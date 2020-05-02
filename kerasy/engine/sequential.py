# -*- coding: utf-8 -*-

from __future__ import absolute_import

import numpy as np

from ..layers import Input
from .base_layer import Layer
from ..layers import Dropout

from .. import optimizers
from .. import losses
from .. import metrics

from ..utils import make_batches
from ..utils import flush_progress_bar
from ..utils import handleTypeError
from ..utils import print_summary
from ..utils import Table
from ..utils import ProgressMonitor
from ..utils import handle_random_state

class Sequential():
    def __init__(self, random_state=None):
        self.layers = []
        self.rnd = handle_random_state(random_state)

    def add(self, layer):
        """Adds a layer instance."""
        if not isinstance(layer, Layer):
            raise TypeError(f"The added layer must be an instance of class Layer. Found: {str(layer)}")
        self.layers.append(layer)

    def compile(self, optimizer, loss, metric):
        """ Creates the layer weights.
        @param optimizer: (String name of optimizer) or (Optimizer instance).
        @param loss     : (String name of loss function) or (Loss instance).
        @param metrics  : (List) Metrics to be evaluated by the model during training and testing.
        """
        self.optimizer = optimizers.get(optimizer)
        self.loss = losses.get(loss)
        self.metrics = metrics.get(metric)
        input_layer = self.layers[0]
        handleTypeError(
            types=[Input], input_layer=input_layer,
            msg_="The initial layer should be Input Layer"
        )
        output_shape = input_layer.input_shape
        for layer in self.layers:
            output_shape = layer.build(output_shape)

    def fit(self,
            x=None, y=None, batch_size=32, epochs=1, verbose=1, shuffle=True,
            validation_spilit=0, validation_data=None, validation_steps=None,
            class_weight=None, sample_weight=None, **kwargs):
        if kwargs:
            raise TypeError(f'Unrecognized keyword arguments: {str(kwargs)}')
        if (x is None) or (y is None):
            raise ValueError('Please specify the trainig data. (x,y)')
        # Prepare validation data.
        do_validation = False
        if validation_data:
            do_validation = True
            if len(validation_data) == 2:
                x_val, y_val = validation_data
                val_sample_weight = None
            elif len(validation_data) == 3:
                x_val, y_val, val_sample_weight = validation_data
            else:
                raise ValueError(f"When passing validation_data, it must contain 2 (x_val, y_val) or 3 (x_val, y_val, val_sample_weights) items. However, it contains {len(validation)} items.")
            num_val_samples = len(x_val)

        # Prepare for the trainig.
        num_train_samples = len(x)
        batches = make_batches(num_train_samples, batch_size)
        num_batchs = len(batches)
        index_array = np.arange(num_train_samples)

        for epoch in range(epochs):
            if shuffle:
                self.rnd.shuffle(index_array)
            monitor = ProgressMonitor(
                max_iter=num_batchs, verbose=verbose,
                barname=f"Epoch {epoch+1:>0{len(str(epochs))}}/{epochs} |"
            )
            losses = 0
            for batch_index, (batch_start, batch_end) in enumerate(batches):
                batch_ids = index_array[batch_start:batch_end]
                for bs, (x_train, y_true) in enumerate(zip(x[batch_ids], y[batch_ids])):
                    y_pred = self.forward_train(x_train)
                    self.backprop(y_true=y_true, y_pred=y_pred)
                    losses += self.metrics.loss(y_true=y_true, y_pred=np.argmax(y_pred))
                self.updates(bs+1)
                # NOTE: This metrics is specialized for MNIST sample.
                metrics = {
                    self.metrics.name: f"{losses/min((batch_index+1)*batch_size, num_train_samples):.1%}",
                }
                monitor.report(it=batch_index, **metrics)
            if do_validation:
                # NOTE: This metrics is specialized for MNIST sample.
                y_val_pred = self.predict(x_val)
                metrics.update({
                    "val_" + self.metrics.name: f"{self.metrics.loss(y_true=y_val, y_pred=np.argmax(y_val_pred, axis=1)):.1%}",
                })
                monitor.report(it=batch_index, **metrics)
            monitor.remove()

    def forward_train(self, input):
        out=input
        for layer in self.layers:
            out = layer.forward(out)
        return out

    def forward_test(self, input):
        out=input
        for layer in self.layers:
            if isinstance(layer, Dropout):
                continue
            out = layer.forward(out)
        return out

    def backprop(self, y_true, y_pred):
        dEdXout = self.loss.diff(y_true, y_pred)
        for layer in reversed(self.layers):
            dEdXout = layer.backprop(dEdXout)

    def predict(self, x_train):
        if np.ndim(x_train) == 1:
            return self.forward_test(x_train)
        else:
            return np.array([self.forward_test(x) for x in x_train])

    def updates(self, batch_size):
        for layer in reversed(self.layers):
            layer.update(self.optimizer, batch_size)

    def summary(self):
        print_summary(self)

    def trainable(self):
        layers = self.layers
        num_layers = len(layers)

        table = Table()
        table.set_cols(colname="id", values=range(num_layers), zero_padding=True, width=len(str(num_layers)))
        table.set_cols(colname="name", values=[l.name for l in layers], align=">")
        table.set_cols(colname="trainable", values=[str(l.trainable) for l in layers], align="^", color="blue")
        table.show()

    def set_ltrainable(self, Layer, trainable):
        for layer in self.layers:
            if isinstance(layer, Layer):
                layer.trainable = trainable
