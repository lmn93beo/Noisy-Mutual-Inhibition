# simulation_module.py
# Module definining activaiton functions, change in state, update to state,
# and a numerical simulation of the solution to a nonlinear dynamical system.

import numpy as np


### Functions for simulation
def thresh_exp(x):
    '''Activation function'''
    return 1 / (1 + np.exp(-x))

def find_dx(state, It, params):
    '''Returns dx/dt given the parameters and current state'''
    Winh = params['Winh']
    Wexc = params['Wexc'] 
    tau = params['tau']
    
    x = state
    dx = (-x + thresh_exp(Winh * x + Wexc * x + It)) / tau
    return dx

def update_x(state, It, params):
    '''Update u based on params'''
    nextState = state
    nextState += find_dx(state, It, params) * params['dt']
    return nextState

def simulate_x(state_init, I0, params, niter):
    '''Simulate for niter iterations'''
    curr_state = state_init
    x_lst = state_init
    
    for i in range(niter):
        It = I0;
        curr_state = update_x(curr_state, It, params)
        x_lst = np.append(x_lst,curr_state, axis=1)
        
    return x_lst

### A Two-neuron module class
## Define an object class for simulation
class TwoNeuronModule:
    def __init__(self, Wut, Wvt, Wuv, Wvu, theta, tau, dt, 
                 sigma_mu, sigma_sigma, threshold, K=0):
        '''Initialize a two-neuron module with parameters:
        Wut, Wvt, Wuv, Wvu: weights of the connections between u, v, and input (theta)
        theta: input
        tau: time constant
        dt: time step for simulation
        sigma_mu: indicates fluctuation in the mean between trials
        sigma_sigma: indicates the noise within each trial
        threshold: threshold for behavior, used to determine tp
        K: constant for updating
        '''
        self.Wut = Wut
        self.Wvt = Wvt
        self.Wuv = Wuv
        self.Wvu = Wvu
        self.theta = theta
        self.tau = tau
        self.dt = dt
        self.sigma_mu = sigma_mu
        self.sigma_sigma = sigma_sigma
        self.ext = 0
        self.threshold = threshold
        self.K = K
 
    def _initialize_state(self, u_init, v_init, ntrials, set_theta, theta):
        '''Initialize n states, each set to (u_init, v_init)
        ****Parameters****
        u_init, v_init: initial state of u and v
        ntrials: number of trials to simulate
        set_theta: if True, reset the default theta
        theta: if set_theta is True, use this theta as the input to the module '''
        self.ustate = np.array([u_init] * ntrials)
        self.vstate = np.array([v_init] * ntrials)
        self.ext = np.random.normal(0, self.sigma_mu, ntrials)
        if set_theta:
            self.theta = theta

    def _find_u_dot_multi(self):
        '''Based on the current state, calculate du/dt'''
        noise = np.random.normal(loc=0, scale=self.sigma_sigma, size=len(self.ustate))
        return (-self.ustate + thresh_exp(self.Wut * self.theta - \
                                          self.Wuv * self.vstate + noise + self.ext)) / self.tau
    
    def _find_v_dot_multi(self):
        '''Based on the current state, calcualte dv/dt'''
        noise = np.random.normal(loc=0, scale=self.sigma_sigma, size=len(self.ustate))
        return (-self.vstate + thresh_exp(self.Wut * self.theta - \
                                          self.Wuv * self.ustate + noise + self.ext)) / self.tau

    def _update_state(self):
        '''Based on the current state, update to the state in the next time step'''
        order = 1 #np.random.randint(0, 2) # Choose to update u or v first
        if order:
            #print('Order is 1')
            ustate = self.ustate + self._find_u_dot_multi() * self.dt
            vstate = self.vstate + self._find_v_dot_multi() * self.dt
            self.ustate = ustate
            self.vstate = vstate
            
        else:
            #print('Not here')
            self.vstate = self.vstate + self._find_v_dot_multi() * self.dt
            self.ustate = self.ustate + self._find_u_dot_multi() * self.dt
    
    def simulate_full_trial(self, u_init, v_init, ntrials, nsteps, set_theta=False, theta=0):
        '''Simulate a full trial
        **** Parameters ****
        u_init, v_init: floats, initial state
        ntrials: int, number of trials to simulate
        nsteps: int, number of steps in each trial
        set_theta: if True, reset the default theta
        theta: if set_theta is True, use this theta as the input to the module
        **** Output ****
        U, V: numpy arrays of dimension ntrials x nsteps,
        the states of u and v over the course of simulation'''
        self._initialize_state(u_init, v_init, ntrials, set_theta, theta)
        self.u_lst = []
        self.v_lst = []
        for i in range(nsteps):
            self.u_lst.append(self.ustate.copy())
            self.v_lst.append(self.vstate.copy())
            self._update_state()
        
        self.u_lst = np.vstack(self.u_lst)
        self.v_lst = np.vstack(self.v_lst)
        return self.u_lst, self.v_lst
    
    def get_decision_v(self):
        '''Returns a numpy array of dimension ntrials x nsteps,
        the projection of the (u, v) state onto the recurrent axis
        '''
        return self.u_lst - self.v_lst
    
    def get_feedback(self, time_feedback):
        '''**** Parameters ****
        time_feedback: int, the time the feedback signal is given
        **** Output ****
        
        '''
        return self.K * (self.get_decision_v()[time_feedback] - self.threshold) 
    
    def find_tp(self):
        decision_v = self.get_decision_v()
        times_lst = []
        for k in range(self.u_lst.shape[1]):
            if np.max(decision_v[:, k]) > self.threshold:
                times_lst.append(np.nonzero(decision_v[:, k] > self.threshold)[0][0])
            else:
                times_lst.append(np.inf)
                
        return np.array(times_lst)

### A class for chained two-neuron modules
# A Class for chained modules
class ChainedTwoNeuronModules:
    def __init__(self, modulelst):
        '''Initialize with modulelst: a list of TwoNeuronModule objects'''
        self.modulelst = modulelst
        # TODO: Threshold, tau and dt constraints?
        
    def find_tp(self):
        total_tp = 0
        for module in self.modulelst:
            total_tp = total_tp + module.find_tp()
        return total_tp
    
    def simulate_full_trial(self, u_init, v_init, ntrials, nsteps, t_feedback):
        for id, module in enumerate(self.modulelst):
            # No update for first module
            if id == 0:
                module.simulate_full_trial(u_init, v_init, ntrials, nsteps)
            else:
                module.simulate_full_trial(u_init, v_init, ntrials, nsteps, True, theta_next)
            
            theta_next = module.theta + module.get_feedback(t_feedback)


## Define an object class for modules with multiple neurons
class MultipleNeuronModule:
    def __init__(self, Wut, Wvt, Wuv, Wvu, theta, tau, dt, 
                 sigma_mu, sigma_sigma, threshold, K=0):
        '''Initialize a two-neuron module with parameters:
        Wut, Wvt, Wuv, Wvu: weights of the connections between u, v, and input (theta)
        theta: input
        tau: time constant
        dt: time step for simulation
        sigma_mu: indicates fluctuation in the mean between trials
        sigma_sigma: indicates the noise within each trial
        threshold: threshold for behavior, used to determine tp
        K: constant for updating
        '''
        self.Wut = Wut
        self.Wvt = Wvt
        self.Wuv = Wuv
        self.Wvu = Wvu
        self.theta = theta
        self.tau = tau
        self.dt = dt
        self.sigma_mu = sigma_mu
        self.sigma_sigma = sigma_sigma
        self.ext = 0
        self.threshold = threshold
        self.K = K
        self.Winh = np.matrix([[0, -Wuv], [-Wvu, 0]])
        self.Wexc = np.matrix([[0, 0], [0, 0]])
        self.state = np.matrix([0])
 
    def _initialize_state(self, u_init, v_init, ntrials, set_theta, theta):
        '''Initialize n states, each set to (u_init, v_init)
        ****Parameters****
        u_init, v_init: initial state of u and v
        ntrials: number of trials to simulate
        set_theta: if True, reset the default theta
        theta: if set_theta is True, use this theta as the input to the module '''
        
        self.ext = np.random.normal(0, self.sigma_mu, ntrials)
        if set_theta:
            self.theta = theta
            
        self.state = np.matrix([[u_init] * ntrials, [v_init] * ntrials])
        
    def _find_dstate(self):
        '''Find the change in the state vector at each update
        Input: It, the current
        Output: vector of dx (including du, dv)'''
        x = self.state
        return (-x + thresh_exp(self.Wut * self.theta + self.Winh * x + self.Wexc * x + self.ext)) / self.tau

    def _find_u_dot_multi(self):
        '''Based on the current state, calculate du/dt'''
        noise = np.random.normal(loc=0, scale=self.sigma_sigma, size=len(self.ustate))
        return (-self.ustate + thresh_exp(self.Wut * self.theta - \
                                          self.Wuv * self.vstate + noise + self.ext)) / self.tau
    
    def _find_v_dot_multi(self):
        '''Based on the current state, calcualte dv/dt'''
        noise = np.random.normal(loc=0, scale=self.sigma_sigma, size=len(self.ustate))
        return (-self.vstate + thresh_exp(self.Wut * self.theta - \
                                          self.Wuv * self.ustate + noise + self.ext)) / self.tau

    def _update_state(self):
        '''Based on the current state, update to the state in the next time step'''
        self.state += self._find_dstate() * self.dt
    
    def simulate_full_trial(self, u_init, v_init, ntrials, nsteps, set_theta=False, theta=0):
        '''Simulate a full trial
        **** Parameters ****
        u_init, v_init: floats, initial state
        ntrials: int, number of trials to simulate
        nsteps: int, number of steps in each trial
        set_theta: if True, reset the default theta
        theta: if set_theta is True, use this theta as the input to the module
        **** Output ****
        U, V: numpy arrays of dimension ntrials x nsteps,
        the states of u and v over the course of simulation'''
        self._initialize_state(u_init, v_init, ntrials, set_theta, theta)
        self.u_lst = []
        self.v_lst = []        
        
        for i in range(nsteps):
            curr_state = self.state.copy()
            ustate_copy = np.squeeze(np.asarray(curr_state[0]))
            vstate_copy = np.squeeze(np.asarray(curr_state[1]))
            self.u_lst.append(ustate_copy)
            self.v_lst.append(vstate_copy)
            self._update_state()
        
        self.u_lst = np.vstack(self.u_lst)
        self.v_lst = np.vstack(self.v_lst)
        return self.u_lst, self.v_lst
    
    def get_decision_v(self):
        '''Returns a numpy array of dimension ntrials x nsteps,
        the projection of the (u, v) state onto the recurrent axis
        '''
        return self.u_lst - self.v_lst
    
    def get_feedback(self, time_feedback):
        '''**** Parameters ****
        time_feedback: int, the time the feedback signal is given
        **** Output ****
        
        '''
        return self.K * (self.get_decision_v()[time_feedback] - self.threshold) 
    
    def find_tp(self):
        decision_v = self.get_decision_v()
        times_lst = []
        for k in range(self.u_lst.shape[1]):
            if np.max(decision_v[:, k]) > self.threshold:
                times_lst.append(np.nonzero(decision_v[:, k] > self.threshold)[0][0])
            else:
                times_lst.append(np.inf)
                
        return np.array(times_lst)
