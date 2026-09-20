import math,numpy as np
scale=30.625025877938
c=math.log(10)/400
def sigmoid(x):return 1/(1+math.exp(-x))
def softmax(x):
    z=np.exp(np.array(x)-max(x));return z/z.sum()
def convolution(a,b):
    n=len(a)+len(b)-1;k=1<<(n-1).bit_length()
    v=np.fft.irfft(np.fft.rfft(a,k)*np.fft.rfft(b,k),k)[:n]
    v=np.maximum(v,0);return v/v.sum()
def two_leg(teams):
    # Discretize weekly performances at 0.1 point, then convolve independent legs.
    distributions=[]
    for t in teams:
        loc=scale*c*(t['elo']-1500)
        low=math.floor((loc-8*scale)*10);high=math.ceil((loc+35*scale)*10)
        x=np.arange(low,high+1)/10
        cdf=lambda v:np.exp(-np.exp(-(v-loc)/scale))
        mass=cdf(x+.05)-cdf(x-.05)
        dist=convolution(mass,mass)
        distributions.append((2*low,dist,np.cumsum(dist)))
    out=[]
    for i,(low,mass,_) in enumerate(distributions):
        values=low+np.arange(len(mass));product=mass.copy()
        for j,(lo,pmf,cdf) in enumerate(distributions):
            if i==j:continue
            idx=values-lo
            le=np.where(idx<0,0,cdf[np.clip(idx,0,len(cdf)-1)])
            lt=np.where(idx-1<0,0,cdf[np.clip(idx-1,0,len(cdf)-1)])
            product*=le if teams[i]['seed']<teams[j]['seed'] else lt if teams[i]['seed']>teams[j]['seed'] else (le+lt)/2
        out.append(float(product.sum()))
    assert abs(sum(out)-1)<1e-8,out
    return out
