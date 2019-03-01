# https://github.com/AppliedDataSciencePartners/DeepReinforcementLearning

import tensorflow as tf
import numpy as np
import os

from tensorflow.keras.models import Sequential, load_model, Model
from tensorflow.keras.layers import Input, Dense, Conv2D, Flatten, BatchNormalization, Activation, LeakyReLU, add
from tensorflow.keras.optimizers import SGD
from tensorflow.keras import regularizers


def softmax_cross_entropy_with_logits(y_true, y_pred):
    p = y_pred
    pi = y_true
    zero = tf.zeros(shape = tf.shape(pi), dtype=tf.float32)
    where = tf.equal(pi, zero)
    negatives = tf.fill(tf.shape(pi), -100.0) 
    p = tf.where(where, negatives, p)
    loss = tf.nn.softmax_cross_entropy_with_logits(labels = pi, logits = p)
    return loss

class Gen_Model():
    def __init__(self):
        self.model          = None

    def predict(self, x):
        return self.model.predict(x)

    def fit(self, states, targets, epochs, verbose, validation_split, batch_size):
        return self.model.fit(
            states, targets, 
            epochs = epochs, verbose = verbose, 
            validation_split = validation_split, 
            batch_size = batch_size
        )

    def save(self, game, version):
        path    = os.path.join('models', game)
        fname   = 'v%s.h5' % version
        if not os.path.exists(path): os.makedirs(path)
        self.model.save(os.path.join(path, fname))

    def load(self, game, version):
        path    = os.path.join('models', game)
        fname   = 'v%s.h5' % version
        self.model = load_model(os.path.join(path, fname))
        return self
        # return load_model(
        #     run_archive_folder + game + '/run' + str(run_number).zfill(4) + "/models/version" + "{0:0>4}".format(version) + '.h5', 
        #     custom_objects = {'softmax_cross_entropy_with_logits': softmax_cross_entropy_with_logits}
        # )

class Residual_CNN(Gen_Model):
    def __init__(self, reg_const, learning_rate, input_dim, output_dim, hidden_layers):
        Gen_Model.__init__(self)
        self.reg_const      = reg_const
        self.learning_rate  = learning_rate
        self.input_dim      = input_dim
        self.output_dim     = output_dim
        self.hidden_layers  = hidden_layers
        self.model          = self._build_model()

    def residual_layer(self, input_block, filters, kernel_size):
        x = self.conv_layer(input_block, filters, kernel_size)
        x = Conv2D(
            filters = filters,
            kernel_size = kernel_size,
            data_format="channels_last",
            padding = 'same',
            use_bias=False,
            activation='linear',
            kernel_regularizer = regularizers.l2(self.reg_const)
        )(x)
        x = BatchNormalization(axis=3)(x)
        x = add([input_block, x])
        x = LeakyReLU()(x)
        return (x)

    def conv_layer(self, x, filters, kernel_size):
        x = Conv2D(
            filters = filters,
            kernel_size = kernel_size,
            data_format="channels_last",
            padding = 'same',
            use_bias=False,
            activation='linear',
            kernel_regularizer = regularizers.l2(self.reg_const)
        )(x)
        x = BatchNormalization(axis=3)(x)
        x = LeakyReLU()(x)
        return (x)

    def value_head(self, x):
        x = Conv2D(
            filters = 1,
            kernel_size = (1,1),
            data_format="channels_last",
            padding = 'same',
            use_bias=False,
            activation='linear',
            kernel_regularizer = regularizers.l2(self.reg_const)
        )(x)
        x = BatchNormalization(axis=3)(x)
        x = LeakyReLU()(x)
        x = Flatten()(x)
        x = Dense(
            20,
            use_bias=False,
            activation='linear',
            kernel_regularizer=regularizers.l2(self.reg_const)
        )(x)
        x = LeakyReLU()(x)
        x = Dense(
            1,
            use_bias=False,
            activation='sigmoid',
            kernel_regularizer=regularizers.l2(self.reg_const),
            name = 'value_head'
        )(x)
        return (x)

    def policy_head(self, x):
        x = Conv2D(
            filters = 2,
            kernel_size = (1,1),
            data_format="channels_last",
            padding = 'same',
            use_bias=False,
            activation='linear',
            kernel_regularizer = regularizers.l2(self.reg_const)
        )(x)
        x = BatchNormalization(axis=3)(x)
        x = LeakyReLU()(x)
        x = Flatten()(x)
        x = Dense(
            self.output_dim,
            use_bias=False,
            activation='softmax',
            kernel_regularizer=regularizers.l2(self.reg_const),
            name = 'policy_head'
        )(x)
        return (x)

    def _build_model(self):
        main_input = Input(shape = self.input_dim, name = 'main_input')
        x = self.conv_layer(main_input, self.hidden_layers[0]['filters'], self.hidden_layers[0]['kernel_size'])
        if len(self.hidden_layers) > 1:
            for h in self.hidden_layers[1:]:
                x = self.residual_layer(x, h['filters'], h['kernel_size'])
        vh = self.value_head(x)
        ph = self.policy_head(x)
        model = Model(inputs=[main_input], outputs=[vh, ph])
        model.compile(
            loss={'value_head': 'binary_crossentropy', 'policy_head': 'categorical_crossentropy'},#softmax_cross_entropy_with_logits},
            optimizer=SGD(lr=self.learning_rate, momentum = 0.9),
            loss_weights={'value_head': 0.5, 'policy_head': 0.5},
            metrics=['accuracy'],
        )
        return model

    def convertToModelInput(self, state):
        inputToModel =  state.binary #np.append(state.binary, [(state.playerTurn + 1)/2] * self.input_dim[1] * self.input_dim[2])
        inputToModel = np.reshape(inputToModel, self.input_dim)
        return (inputToModel)