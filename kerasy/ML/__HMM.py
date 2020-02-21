#coding: utf-8
from __future__ import absolute_import

import os
import numpy as np
from scipy.special import logsumexp
import warnings

from ..utils import Params
from ..utils import flush_progress_bar
from ..utils import handleKeyError
from ..utils import handle_random_state
from ..utils import has_not_attrs
from ..utils import normalize, log_normalize
from ..clib import c_hmm

DECODER_ALGORITHMS = ["map", "viterbi"]

def iter_from_variable_len_samples(X, lengths=None):
    """ yield starts and ends indexes of `X` per variable sample.
    Each sample should have the `n_features` features.
    np.sum(`lengths`) must be equal to `n_samples`
    =============================================================
    @params X       : Multiple connected samples. shape=(n_samples, n_features)
    @params lengths : int array. shape=(n_sequences)
    """
    if lengths is None:
        yield 0, len(X)
    else:
        n_samples = X.shape[0]
        end = np.cumsum(lengths).astype(np.int32)
        start = end - lengths
        if end[-1] > n_samples:
            raise ValueError("more than {:d} samples in lengths array {!s}".format(n_samples, lengths))
        for i in range(len(lengths)):
            yield start[i], end[i]

class BaseHMM(Params):
    """ Hidden Markov Model.
    @attr n_hstates : (int) Number of hidden states.
    @attr n_states  : (int) Number of possible symbols emitted by the model.
    @attr initial   : Initial hidden states probabilities. shape=(n_hstates)
    @attr transit   : transition probabilities between hidden states. shape=(n_hstates, n_hstates)
    @attr emission  : The emission probability per each hidden states. shape=(n_hstates, n_states)
    """
    def __init__(self, n_hstates=3, init="random", algorithm="viterbi", random_state=None):
        """
        @params n_hstates    : (int) Number of hidden states.
        @params init         : (str) `path`, 'random'
        @params random_state : (int) random state for initialization.
        """
        super().__init__()
        self.n_hstates = n_hstates
        self.init = init
        self.algorithm = algorithm
        self.seed = random_state
        self.history = []

    def _check_and_get_n_states(self, X):
        """  """
        if not np.issubdtype(X.dtype, np.integer):
            raise ValueError("Symbols should be integers")
        if X.min() < 0:
            raise ValueError("Symbols should be nonnegative")
        if hasattr(self, "n_states"):
            if self.n_states-1 < X.max():
                raise ValueError(
                    "Largest symbol is {} but the model only emits "
                    "symbols up to {}"
                    .format(X.max(), self.n_states-1))
        n_states = X.max()+1
        return n_states

    def _init_params(self, X, init):
        """ Initialize the parameters """
        self.n_states = self._check_and_get_n_states(X)
        if init=="random":
            rnd = np.random.RandomState(self.seed)
            self.initial = rnd.rand(n_hstates)
            normalize(self.initial)
            self.transit = rnd.rand(self.n_hstates, self.n_hstates) + np.diag(np.ones(shape=self.n_hstates)*0.3)
            normalize(self.transit, axis=1)
            self.emission = rnd.rand(self.n_hstates, self.n_states)
            normalize(self.emission)
        elif os.path.exists(init):
            self.load_params(init)
            remain_attrs = has_not_attrs(self, "initial", "transit", "emission")
            if len(remain_attrs)>0:
                for attr in remain_attrs:
                    warnings.warn(f"`{}` is not described in {init}, please specify it in the file, or self.{}=SOMETHING to define it.")
        else:
            raise ValueError(f"the `init` parameter should be 'random', or 'path/to/json', but got {init})

    def _compute_log_likelihood(self, X):
        """ Computes per-component log probability under the model.
        @params X             : Multiple connected samples. shape=(n_samples, n_features)
        @params log_cond_prob : Log conditional probabilities. shape=(n_samples, n_hstates)
        """
        raise NotImplementedError("This class is Abstract")

    def _mstep(self):
        raise NotImplementedError("This class is Abstract.")

    def fit(self, X, lengths=None, max_iter=10, tol=1e-4, verbose=1):
        """ Baum-Welch Algorithm
        @params X       : Multiple connected samples. shape=(n_samples, n_features)
        @params lengths : int array. shape=(n_sequences)
        """
        self._init_params(X, self.init)
        self._check_params_validity()
        for it in range(max_iter):
            current_log_prob = 0.
            for i,j in iter_from_X_lengths(X, lengths):
                # log conditional probability (start with ith)
                log_cond_prob_ij = self._compute_log_likelihood(X[i:j])
                log_prob, log_alpha = self._Estep_log_forward(log_cond_prob_ij)
                current_log_prob += log_prob
                log_beta = self._Estep_log_backward(log_cond_prob_ij)
                posteriors = self._compute_posteriors(log_alpha, bwdlattice)
                # TODO: Update parameters.
                # self._accumulate_sufficient_statistics(stats, X[i:j], log_cond_prob_ij, posteriors, log_alpha, log_beta)
            flush_progress_bar(it, max_iter, metrics={"log probability": current_log_prob}, barname="Baum-Welch Algorithm")
            self._mstep()
            if "CONDITION":
                break
        return

    def score_samples(self, X, length=None):
        """ Compute the posterior probability for each hidden state.
        @params X       : Multiple connected samples. shape=(n_samples, n_features)
        @params lengths : int array. shape=(n_sequences)
        """
        self._check_params_validity()
        n_samples = X.shape
        log_prob = 0.
        posterior_prob = np.empty(shape=(n_samples, self.n_hstates))
        for i,j in iter_from_X_lengths(X, lengths):
            log_cond_prob_ij = self._compute_log_likelihood(X[i:j])
            log_prob, log_alpha = self._Estep_log_forward(log_cond_prob_ij)
            log_prob += log_prob_ij

            log_beta = self._Estep_log_backward(log_cond_prob_ij)
            posterior_prob[i:j] = self._compute_posteriors(log_alpha, log_beta)
        return log_prob, posterior_prob

    def score(self, X, length=None):
        """ Compute the log likelihood under the model parameters.
        @params X       : Multiple connected samples. shape=(n_samples, n_features)
        @params lengths : int array. shape=(n_sequences)
        """
        self._check_params_validity()
        log_prob = 0.
        for i,j in iter_from_X_lengths(X, lengths):
            log_cond_prob_ij = self._compute_log_likelihood(X[i:j])
            log_prob_ij, _ = self._Estep_log_forward(log_cond_prob_ij)
            log_prob += log_prob_ij
        return log_prob

    def _decode_viterbi(self, X):
        """ Decode by viterbi algorithm. """
        log_cond_prob = self._compute_log_likelihood(X)
        # logprob, ml_hstates = self._viterbi(log_cond_prob)
        return self._viterbi(log_cond_prob)

    def _decode_map(self, X):
        """ Decode by MAP(Maximum A Posteriori) estimation """
        _, posterior_prob = self.score_samples(X)
        log_prob = np.max(posterior_prob, axis=1).sum()
        ml_hstates = np.argmax(posteriors, axis=1)
        return logprob, ml_hstates

    def decode(self, X, lengths=None, algorithm=None):
        """ Find the maximum likelihood hidden state sequences. """
        self.check()
        # The value of the preceding variable takes precedence.
        # Therefore, this code is same as the followings.
        # `algorithm = self.algorithm if algorithm is None else algoritm`
        algorithm = (algorithm or self.algorithm).lower()
        if algorithm not in ["viterbi", ]:
            handleKeyError(DECODER_ALGORITHMS, algorithm=algorithm)
        decode_func = {
            "viterbi": self._decode_viterbi,
            "map": self._decode_map
        }[algorithm]

        n_samples = X.shape[0]
        log_prob = 0
        ml_hstates = np.empty(n_samples, dtype=int)
        for i, j in iter_from_variable_len_samples(X, lengths):
            log_prob_ij, ml_hstates_ij = decode_func(X[i:j])
            log_prob += log_prob_ij
            state_sequence[i:j] = ml_hstates_ij
        return log_prob, ml_hstates

    def predict(self, X, lengths=None, algorithm=None):
        """ Find Maximum likelihood hidden state sequences. """
        _, ml_hstates = self.decode(X, lengths, algorithm=algorithm)
        return ml_hstates

    def predict_proba(self, X, lengths=None):
        """ Compute the posterior probability for each hidden state. """
        _, posterior_prob = self.score_samples(X, lengths)
        return posterior_prob

    def sample(self, n_samples=1, random_state=None, verbose=1):
        """Generate random samples from the model.
        @params n_samples    : (int) Number of samples to generate.
        @params random_state : (int) seed.
        """
        self._check_params_validity()
        rnd = handle_random_state(self.seed if random_state is None else random_state)

        transit = self.transit
        hidden_states = np.arange(self.n_hstates)

        # Initialization.
        h_state_sequences = np.empty(shape=n_samples, dtype=int)
        h_state_sequences[0] = h_state = self.initial.argmax()
        samples = [self._generate_sample(h_state, random_state=rnd)]
        flush_progress_bar(0, n_samples, metrics={"hidden state": h_state})
        for n in range(1, n_samples):
            h_state_sequences[n] = h_state = rnd.choice(a=hidden_states, p=transit[h_state])
            samples.append(self._generate_sample(h_state, random_state=rnd))
            flush_progress_bar(n, n_samples, metrics={"hidden state": h_state})

        return np.atleast_2d(samples), np.asarray(h_state_sequences, dtype=int)

    def _viterbi(self, log_cond_prob):
        """ viterbi algorithm.
        @params log_cond_prob    : Log conditional probabilities. shape=(n_samples, n_hstates)
        @return log_prob         : Log scaled probability if the states were emitted from `ml_hstates`.
        @return ml_hstates       : Maximum likelihood hidden state sequences. shape=(n_samples)
        """
        ml_hstates, log_prob = c_hmm._log_forward(
            log_mask_zero(self.initial),
            log_mask_zero(self.transit),
            log_cond_prob
        )
        return logprob, ml_hstates

    def _Estep_log_forward(self, log_cond_prob):
        """ Log-scaled forward algorithm.
        @params log_cond_prob : Log conditional probabilities. p(x_n,z_n) shape=(n_samples, n_hstates)
        @return log_prob      : Log scaled probability. p(X)
        @return log_alpha     : Log scaled alpha. shape=(n_samples, n_hstates)
        """
        log_alpha = c_hmm._log_forward(
            log_mask_zero(self.initial),
            log_mask_zero(self.transit),
            log_cond_prob
        )
        with np.errstate(under="ignore"):
            # (PRML 13.42) p(X) = sum_{z_N}(alpha(z_N))
            log_prob = logsumexp(log_alpha[-1])
            return log_prob, log_alpha

    def _Estep_log_backward(self, log_cond_prob):
        """ Log-scaled backward algorithm.
        @params log_cond_prob : Log conditional probabilities. p(x_n,z_n) shape=(n_samples, n_hstates)
        @return log_beta      : Log scaled beta. shape=(n_samples, n_hstates)
        """
        log_beta = c_hmm._log_backward(
            log_mask_zero(self.initial),
            log_mask_zero(self.transit),
            log_cond_prob
        )
        return log_beta

    def _compute_posteriors(self, log_alpha, log_beta):
        """ Compute log-scaled gamma(z_n) = p(z_n|X) = p(X|z_n)*p(z_n) / p(X) """
        # (PRML 13.33) gamma(z_n) = alpha(z_n)*beta(z_n) / p(X)
        log_gamma = log_alpha + log_beta
        log_normalize(log_gamma, axos=1)
        with np.errstate(under="ifnore"):
            return np.exp(log_gamma)

class MultinomialHMM(BaseHMM):
    """ Hidden Markov Model with multinomial (discrete) emissions """
    def __init__(self, n_hstates=3, init="random", random_state=None):
        super().__init__(n_hstates=n_hstates, init=init, random_state=random_state)

    def fit(self, X, length=None, epochs=1, verbose=1, rtol=1e-7):
        """
        @params X       :
        @params lengths :
        """
        pMLL = 0 # post Mean Log Likelihood
        N = len(X)
        for epoch in range(epochs):
            pis  = np.zeros(shape=(0,*self.initial.shape))
            As   = np.zeros(shape=(0,*self.transit.shape))
            phis = np.zeros(shape=(0,*self.emission.shape))
            for sequence in X:
                gamma, xi = self.Estep(sequence) # E step
                pi,A,phi = self._Mstep(gamma,xi,sequence) # M step (Not update now)
                pis = np.r_[pis,pi[None,:]]; As = np.r_[As,A[None,:,:]]; phis = np.r_[phis,phi[None,:,:]]

            # Update.
            self.initial  = np.mean(pis,  axis=0)
            self.transit  = np.mean(As,   axis=0)
            self.emission = np.mean(phis, axis=0)

            LLs=0 # Log Likelihood
            for sequence in X:
                LLs+=self.Estep(sequence, only_LL=True)
            MLL = LLs/N
            flush_progress_bar(epoch, epochs, metrics={"Log likelihood": MLL}, verbose=verbose)
            self.epoch+=1
            self.history.append(MLL)
            if abs(MLL-pMLL)<rtol:
                break
            pMLL=MLL
        if verbose: print()

    def Estep(self, sequence, only_LL=False):
        """Calcurate the γ and ξ for M step."""
        N = len(sequence)
        alpha = np.zeros(shape=(N,self.n_hstates))
        beta  = np.zeros(shape=(N,self.n_hstates))
        c = np.zeros(shape=(N,)) # scaling factor.

        #=== Forward Algorithm ===
        # Initialization
        alpha[0] = self.initial * self.emission[:,sequence[0]] # α(z1) = p(z1)p(x1|z1) = p(x1,z1)
        c[0] = np.sum(alpha[0]) # c1 = ∑p(x1,z1) = p(x1)
        alpha[0] /= c[0] # α'(z1) = α(z1)/c1 = p(x1,z1)/p(x1) = p(z1|x1)
        # Recursion
        for i in range(1, N):
            # α(zn) = p(xn|zn) ∑p(zn-1|x1,...,xn-1)p(zn|zn-1) = p(xn,zn|x1,...,xn-1)
            alpha[i] = self.emission[:,sequence[i]] * alpha[i-1].dot(self.transit)
            c[i] = np.sum(alpha[i]) # ci = ∑p(xn,zn|x1,...,xn-1) = p(xn|x1,...,xn-1)
            alpha[i] /= c[i] # α'(z1) = p(xn,zn|x1,...,xn-1)/p(xn|x1,...,xn-1) = p(zn|x1,...,xn)

        if only_LL: return np.sum(np.log(c)) # np.log(np.prod(c))

        #=== Backward Algorithm ===
        # Initialization
        beta[-1] = 1 # β(zN) = 1
        # Recursion
        for i in reversed(range(N-1)):
            # β(zn)  = ∑ β(zn+1)p(xn+1|zn+1)p(zn+1|zn)
            beta[i]  = (beta[i+1]*self.emission[:,sequence[i+1]]).dot(self.transit.T)
            beta[i] /= c[i+1]

        gamma  = alpha * beta # γi = α(zi)β(zi) shape=(N,K)
        xi  =  (1/c[1:, None, None]) * alpha[:-1,:,None] * self.emission[:,sequence[1:]].T[:,None,:] * self.transit[None,:,:] * beta[1:,None,:] # shape=(N-1,Kb,Ka)
        return gamma, xi

    def Mstep(self,gamma,xi,sequence):
        """ Update the params on the fly. """
        # Update the "initial state"; πk=γ_1k/∑γ_1k
        self.initial = gamma[0] / np.sum(gamma[0])

        # Update the "transition probability"; Ajk=∑ξ_ijk/∑∑ξijk
        self.transit  = np.sum(xi, axis=0) / np.sum(xi, axis=(0,2))[:,None] # shape=(Kb,Ka) / shape=(Kb)[:,None] → shape=(Kb,1)

        # Update the emission probability; ϕ_kj=∑γ_ik*x_ij/∑∑γ_ik * x_ij
        x   = gamma[:,None,:] * (np.eye(self.n_states)[sequence])[:,:,None] # shape=(N,K,M)
        self.emission = (np.sum(x, axis=0) / np.sum(gamma, axis=0)).T # shape=(K,M)

    def _Mstep(self,gamma,xi,sequence):
        """ Don't update on the fly """
        pi  = gamma[0] / np.sum(gamma[0])
        A   = np.sum(xi, axis=0) / np.sum(xi, axis=(0,2))[:,None]
        x   = gamma[:,None,:] * (np.eye(self.n_states)[sequence])[:,:,None]
        phi = (np.sum(x, axis=0) / np.sum(gamma, axis=0)).T
        return (pi,A,phi)

    def predict(self, X, asai=True):
        """
        Viterbi algorithm: DP for finding the most likely sequence of hidden states.
        ============================================================================
        @val A[i][j]: The transition probability (s_i → s_j)
        @val φ[i][j]: The emission probability (s_i emmits jth alhpabet.)
        """
        predictions=[]
        X = [np.array([self.base2int[s] for s in seq]) for seq in X]
        for sequence in X:
            N = len(sequence)
            v = np.zeros(shape=(N, self.n_hstates))
            v[0] = self.emission[:, sequence[0]] * self.initial
            for i in range(1, N):
                v[i] = self.emission[:, sequence[i]] * np.max(v[i-1]*self.transit.T, axis=1)
                v[i] /= np.mean(v[i])

            # Traceback
            indexes = np.zeros(shape=(N,), dtype=int)
            indexes[-1] = np.argmax(v[-1])
            for i in reversed(range(N-1)):
                indexes[i] = np.argmax((v[i]*self.transit.T)[indexes[i+1]])
            prediction = "".join((indexes+asai).astype(str))
            predictions.append(prediction)
        return predictions

    def MCK(self, X):
        """ Marginalized Count Kernel """
        X = [np.array([self.base2int[s] for s in seq]) for seq in X]
        MCKs = np.zeros(shape=(0,self.n_states,self.n_hstates))
        for sequence in X:
            N = len(sequence)
            gamma, _ = self.Estep(sequence) # shape=(N,K)
            MCK = 1/N * np.eye(self.n_states)[sequence].T.dot(gamma) # (M,N)@(N,K)=(M,K)
            MCKs = np.r_[MCKs, MCK[None,:,:]]
        return MCKs

#=================================================================
# NOTE: Function to display parameters beautifully. Not necessary
    def params(self):
        length = self.indent + 7*self.n_hstates
        """print the model's parameters"""
        print("【Parameter】"); print("=" * length)
        print("*initial state"); self.initial_state(indent=True); print("-" * length)
        print("*transition probability matrix"); self.translation_prob(); print("-" * length)
        print("*emission probability"); self.emission_prob(indent=True)

    def initial_state(self, indent=False):
        z_format = ""
        for k in range(self.n_hstates):
            z_format += f"{f'z({k+1})':^7}"
        print(f"{' '*self.indent if indent else ''}{z_format}")

        pi_format = ""
        for k in range(self.n_hstates):
            pi_format += f"{self.initial[k]:.4f} "
        print(f"{' '*self.indent if indent else ''}{pi_format}")

    def translation_prob(self):
        print(f"{' '*self.indent}{'[States after transition]':^{7*self.n_hstates}}")
        z_format = ""
        for k in range(self.n_hstates):
            z_format += f"{f'z({k+1})':^7}"
        print(f"{' '*self.indent}{z_format}")

        for j in range(self.n_hstates):
            A_form = f"{f'z({j+1})':^{self.indent}}"
            for k in range(self.n_hstates):
                A_form += f"{self.transit[j][k]:.4f} "
            print(A_form)

    def emission_prob(self, indent=False):
        width = self.indent-1 if indent else max([len(str(d)) for d in self.base2int.keys()])

        z_format  = ""
        for k in range(self.n_hstates):
            z_format += f"{f'z({k+1})':^7}"
        print(f"{' '*self.indent if indent else ' '*(width+1)}{z_format}")

        for j in range(self.n_states):
            phi_form = f"{self.int2base[j]:>{width}} "
            for k in range(self.n_hstates):
                phi_form += f"{self.emission[k][j]:.4f} "
            print(phi_form)
