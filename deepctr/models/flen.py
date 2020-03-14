# -*- coding:utf-8 -*-
"""
Author:
    Tingyi Tan,5636374@qq.com

Reference:
    [1] hen W, Zhan L, Ci Y, Lin C https://arxiv.org/pdf/1911.04690

"""


from itertools import chain
import tensorflow as tf
from tensorflow.python.keras.layers import Flatten

from ..inputs import input_from_feature_columns, get_linear_logit, build_input_features, combined_dnn_input
from ..layers.core import PredictionLayer, DNN
from ..layers.utils import concat_func, add_func
from ..layers.interaction import FieldWiseBiInteraction


def FLEN(linear_feature_columns,
          dnn_feature_columns,
          l2_reg_linear=0.00001,
          l2_reg_embedding=0.00001,
          l2_reg_dnn=0.00001,
          l2_reg_fw=0.00001,
          init_std=0.0001,
          seed=1024,
          dnn_dropout=0.2,
          dnn_activation='relu',
          dnn_use_bn=True,
          task='binary'):
    """Instantiates the DeepFM Network architecture.

    :param linear_feature_columns: An iterable containing all the features used by linear part of the model.
    :param dnn_feature_columns: An iterable containing all the features used by deep part of the model.
    :param l2_reg_linear: float. L2 regularizer strength applied to linear part
    :param l2_reg_embedding: float. L2 regularizer strength applied to embedding vector
    :param l2_reg_dnn: float. L2 regularizer strength applied to DNN
    :param l2_reg_fw: float. L2 regularizer strength applied to fwfm
    :param init_std: float,to use as the initialize std of embedding vector
    :param seed: integer ,to use as random seed.
    :param dnn_dropout: float in [0,1), the probability we will drop out a given DNN coordinate.
    :param dnn_activation: Activation function to use in DNN
    :param dnn_use_bn: bool. Whether use BatchNormalization before activation or not in DNN
    :param task: str, ``"binary"`` for  binary logloss or  ``"regression"`` for regression loss
    :return: A Keras model instance.
    """

    features = build_input_features(linear_feature_columns +
                                    dnn_feature_columns)

    inputs_list = list(features.values())

    group_embedding_dict, dense_value_list = input_from_feature_columns(
        features,
        dnn_feature_columns,
        l2_reg_embedding,
        init_std,
        seed,
        support_group=True)

    # S
    linear_logit = get_linear_logit(features,
                                    linear_feature_columns,
                                    init_std=init_std,
                                    seed=seed,
                                    prefix='linear',
                                    l2_reg=l2_reg_linear)
    linear_logit = Flatten()(linear_logit)

    # FM + MF
    fm_mf_out = FieldWiseBiInteraction(l2_reg=l2_reg_fw, seed=seed)(
        [concat_func(v, axis=1) for k, v in group_embedding_dict.items()])
    fm_mf_out = DNN((32,), dnn_activation, l2_reg_dnn, dnn_dropout,
                    dnn_use_bn, seed)(fm_mf_out)

    # MLP
    mlp_input = combined_dnn_input(
        list(chain.from_iterable(group_embedding_dict.values())),
        dense_value_list)
    mlp_output = DNN((64,), dnn_activation, l2_reg_dnn, dnn_dropout,
                     dnn_use_bn, seed)(mlp_input)
    mlp_output = DNN((32,), dnn_activation, l2_reg_dnn, dnn_dropout,
                     dnn_use_bn, seed)(mlp_output)

    # DNN
    dnn_input = combined_dnn_input([fm_mf_out, mlp_output, linear_logit], dense_value_list)
    dnn_output = dnn_input
    dnn_logit = tf.keras.layers.Dense(1, use_bias=False, activation=None)(dnn_output)
    output = PredictionLayer(task)(dnn_logit)

    model = tf.keras.models.Model(inputs=inputs_list, outputs=output)
    return model