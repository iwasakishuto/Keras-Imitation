# coding: utf-8
import numpy as np

class Linear():
    def forward(input):
        return input

    def diff(delta):
        return delta

class Softmax():
    def forward(input):
        if np.ndim(input) == 1:
            return np.exp(input)/np.sum(np.exp(input), axis=0)
        elif np.ndim(input) == 2:
            print(input)

    def diff(delta):
        return 0

class Tanh():
    def forward(input):
        return np.tanh(input)

    def diff(delta):
        return 1-np.tanh(delta)**2

class Relu():
    def forward(input):
        return np.where(input>0, input, 0)
    
    def diff(delta):
        return np.where(input>0, 1, 0)
    
ActivationHandler = {
    'linear' : Linear,
    'softmax': Softmax,
    'tanh'   : Tanh,
    'relu'   : Relu,
}

def ActivationFunc(activation_func_name):
    return ActivationHandler[activation_func_name]
