"""Selected zero-mean/unit-variance NIG weekly noise; original SD unchanged."""
from pathlib import Path
import json,numpy as np

def standardized_nig(rng,shape,size,normal=None):
 a,ratio=map(float,shape);b=a*ratio
 if not np.isfinite([a,b]).all() or a<=0 or abs(b)>=a:raise ValueError('Invalid NIG shape')
 gamma=np.sqrt(a*a-b*b);v=rng.wald(1/gamma,1,size=size)
 x=b*v+np.sqrt(v)*(rng.normal(size=size) if normal is None else normal)
 return (x-b/gamma)/(a/gamma**1.5)

def parameters(root,data,season):
 # Compatibility accessor; the production shape is fitted with unified noise.
 f=json.loads((Path(root)/'data/adl_scoring_model.json').read_text())[str(season)]
 return dict(shape=f['shape'],scale=1.,training_years=f['innovation_training_years'])
