A simple [bayesian network](https://en.wikipedia.org/wiki/Bayesian_network) implementation. Can be accessed through command line or in a python script.

# Requirements
- python >= 3.8

# Installation
Copy this directory to your custom python site-packages, which you can find by executing
```
python -m site --user-site
```

# Usage
First generate a .bn file with your network using
```
python -m BN -g myBN.bn 'node1|parent1' 'node2|parent1,parent2' ...
```
Not explicitly specified nodes, which appear as parents, are generated automatically as nodes without parents.

Then import in python as:
```
from BN import BN

net = BN('myBN.bn')
net.P('node2')
```
See `examples.py` for more examples.

Querying using commandline:
```
python -m BN myBN.bn 'node1|parent2=t'
```
