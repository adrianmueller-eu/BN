#!/usr/bin/env python3

import re, copy, itertools

class BN:
    """
    A Bayesian Network.

    Data structure(s):
        dictionary that maps variable names to a dictonary {
                parents -> list of parents
                children -> list of children
                prob -> probability of the variable if it's independent, else None
                condprob -> dictionary for the conditionary probability table {
                        tuple of values for parents -> probability
                    }
            }

        e.g. for test_example.bn
        {
            'A': {
                'parents': [],
                'children': ['C', 'D'],
                'prob': 0.3,
                'condprob': {}
            },

            ...

            'D': {
                'parents': ['A', 'B'],
                'children': [],
                'prob': -1,
                'condprob': {
                    (True, True): 0.7,
                    (True, False): 0.8,
                    ...
                }
            }
        }
    """
    def __init__(self, fname=None):
        """
        Initialize the network; read and parse the given file.

        Args:
            fname:  Name of the file containing the data.
        """
        self.permutationsmemo = {}
        self.net = {}
        if not fname:
            return

        lines = []  # buffer
        try:
            with open(fname) as f:
                for line in f:
                    if line == '\n':
                        # parse the buffer if encounter a blank line
                        self._parse(lines)
                        lines = []
                    else:
                        lines.append(line)
            # there is no blank line at the end of file
            # but we still have to parse the last block/buffer
            if len(lines) != 0:
                self._parse(lines)
        except Exception as e:
            print(f"Please give a valid BN file! See test .bn files for guidance.")
            raise e


    def _parse(self, lines):
        """
        Parse the line(s) comprising a node and add the data to the net.

        Args:
            lines:  Buffer/list of lines.
        """
        if len(lines) == 1:
            # single line node/buffer
            match = re.match(r'P\(([^:=]*)[^\)]*\) ?= ?(.*)\n', lines[0])
            var, prob = match.group(1).strip(), float(match.group(2).strip())
            self.addNode(var, None, prob)
        else:
            # multi line node/buffer
            # table header
            match = re.match(r'(.*) \| (.*)', lines[0])
            var, parents = match.group(1).strip(), match.group(2).split()

            prob_dict = {}
            for probline in lines[2:]:
                match = re.match(r'(.*) \| (.*)', probline)
                truth, prob = match.group(1).split(), float(match.group(2).strip())
                truth = tuple(True if x == 't' or x == '1' else False for x in truth)
                prob_dict[truth] = prob

            self.addNode(var, parents, prob_dict)

    def addNode(self, name, parents, prob):
        """
        Add a new node to the graph.

        Args:
            name: Name of the node
            parents: List of parents
            prob: Dict: tuple(Booleans) -> float, or list of probabilities (for name == True) in the order: e.g. with 2 parents
                t t
                t f
                f t
                f f
        """
        if not parents:
            try:
                prob = prob[0]
            except:
                assert type(prob) == float or type(prob) == int

            self.net[name] = {
                'parents': [], 
                'children': [],
                'prob': prob,
                'condprob': {}
            }
        else:
            truth_table = list(itertools.product([True, False], repeat=len(parents)))
            assert len(prob) == len(truth_table), "Not all values specified!"
            for p in parents:
                if p not in self.net:
                    raise ValueError("Parent " + p + " is not defined in the graph!")
                self.net[p]['children'].append(name)

            if type(prob) == dict:
                condprob = prob
            else:
                condprob = {truth: p for truth, p in zip(truth_table, prob)}

            self.net[name] = {
                'parents': parents,
                'children': [],
                'prob': -1,
                'condprob': condprob
            }

    def normalize(self, dist):
        """
        Normalize the probability values so that they add up to 1.0.

        Args:
            dist:   List of probability values.

        Returns:
            Tuple of normalized values.
        """
        return tuple(x * 1/(sum(dist)) for x in dist)

    def toposort(self):
        """
        Run a topological sort to determine the order of the variables.
        All parents of a node has to be added before the node is added, and ties
        are broken alphabetically.
        """
        variables = list(self.net.keys())
        variables.sort()
        s = set()   # used to mark variables
        l = []
        while len(s) < len(variables):
            for v in variables:
                if v not in s and all(x in s for x in self.net[v]['parents']):
                    # add the variable `v` into the set `s` iff
                    # all parents of `v` are already in `s`.
                    s.add(v)
                    l.append(v)
        return l

    def querygiven(self, Y, e):
        """
        Query P(Y | e), or the probability of the variable `Y`, given the
        evidence set `e`, extended with the value of `Y`. All immediate parents
        of Y have to be in `e`.

        Args:
            Y:  The variable for which we calculate the probability distribution.
            e:  The evidence set in the form of a dictionary 
                    { string name: boolean value }, extended with the value of Y.

        Returns:
            A single double representing the probability that Y has the specified value.

        Example: query the probability that A is False given B is False and E is True.
        >>> net = Net('alarm.bn')
        >>> e = {'B': False, 'E': True, 'A': False}
        >>> net.querygiven('A', e)
        0.71
        """
        # Y has no parents
        if self.net[Y]['prob'] != -1:
            prob = self.net[Y]['prob'] if e[Y] else 1 - self.net[Y]['prob']

        # Y has at least 1 parent
        else:
            # get the value of parents of Y
            parents = tuple(e[p] for p in self.net[Y]['parents'])

            # query for prob of Y = y
            prob = self.net[Y]['condprob'][parents] if e[Y] else 1 - self.net[Y]['condprob'][parents]
        return prob

    def genpermutations(self, length):
        """
        Generate tuples of boolean values that have the specified length.

        Returns:
            A list of 2^length distinct tuples.
        """
        assert(length >= 0)
        if length in self.permutationsmemo:
            return self.permutationsmemo[length]
        else:
            perms = set()
            for comb in itertools.combinations_with_replacement([False, True], length):
                for perm in itertools.permutations(comb):
                    perms.add(perm)
            perms = list(perms)
                # perms = [(False, False, False), (False, False, True), ...]
            assert(len(perms) == pow(2, length))

            self.permutationsmemo[length] = perms
            return perms


    def makefactor(self, var, factorvars, e):
        """
        Make a factor with the factorvars[var] variables.

        Args:
            var:    The currently selected variable.
            factorvars: Dictionary of factor variables for the selected var.
            e:      Dictionary of the evidence set

        Returns:
            tuple (list, dict) where
                list: list of variables in alphabetical order
                dict: mapping {tuple: float} where
                    tuple: tuple of True/False values corresponding to the variables
                    float: probability
        """
        variables = factorvars[var]
        variables.sort() 
        # for 'D' in example.bn: ['A', 'D']
        # This is gonna be the keys for the factor
        # (True, True): a => A=t, D=t, prob = a

        allvars = copy.deepcopy(self.net[var]['parents'])
        allvars.append(var)
        # This is the list of all variables involved including those that are in
        # the evidence set.
        # for 'D' in example.bn: ['A', 'B', 'D']

        # Generate the factor entries:
        # 1. Generate all possible permutations of values of the variables
        #   e.g. A=t,B=t,D=t; A=t,B=t,D=f; ...

        perms = self.genpermutations(len(allvars))

        # 2. We take into account the variables that are already in the evidence
        # set by filtering out permutations that does not conform to the values
        # that the variables already have.
        #   e.g. B=t in e then we filter out permutations that have B=f.
        entries = {}
        asg = {}
        for perm in perms:
            violate = False
            for pair in zip(allvars, perm): # tuples of ('var', value)
                if pair[0] in e and e[pair[0]] != pair[1]:
                    violate = True
                    break
                asg[pair[0]] = pair[1]

            if violate:
                continue

        # 3. Based on the remaining permutations we generate entries for the
        # factor.
        #   e.g. A=t,B=t,D=t then we have A=t,D=t with prob 0.7
        #        A=f,B=t,D=f then we have A=f,D=f with prob 0.9
            key = tuple(asg[v] for v in variables)
            prob = self.querygiven(var, asg)
            entries[key] = prob

        return (variables, entries)

    def pointwise(self, var, factor1, factor2):
        """
        Pointwise-product of factors that contain a common variable.

        Args:
            var:    common variable
            factors:    List of factors

        Returns:
            list of new factors
        """
        newvariables = []
        newvariables.extend(factor1[0])
        newvariables.extend(factor2[0])
        newvariables = list(set(newvariables))
        newvariables.sort()

        perms = self.genpermutations(len(newvariables))
        newtable = {}
        asg = {}
        for perm in perms:
            for pair in zip(newvariables, perm):
                asg[pair[0]] = pair[1]
            key = tuple(asg[v] for v in newvariables)
            key1 = tuple(asg[v] for v in factor1[0])
            key2 = tuple(asg[v] for v in factor2[0])
            prob = factor1[1][key1] * factor2[1][key2]
            newtable[key] = prob

        return (newvariables, newtable)

    def sumout(self, var, factors):
        """
        Sum out factors based on var.

        Args:
            var:    The selected variable.
            factors:    List of factors in form of ([vars], {entries})

        Returns:
            A new list of summed out factors.
        """
        # POINTWISE
        pwfactors = []  # list of factors containing var
        indices = []
        for i, factor in enumerate(factors):
            if var in factor[0]:
                pwfactors.append(factor)
                indices.append(i)
        if len(pwfactors) > 1:
            for i in reversed(indices):
                del factors[i]
            result = pwfactors[0]
            for factor in pwfactors[1:]:
                result = self.pointwise(var, result, factor)
            factors.append(result)

        # SUM OUT
        # for each factor
        for i, factor in enumerate(factors):
            # for each variable in the factor's variable list
            for j, v in enumerate(factor[0]):
                # if the variable is hidden
                if v == var:

                    # variable list of the new factor
                    newvariables = factor[0][:j] + factor[0][j+1:]

                    # probability table of the new factor
                    newentries = {}
                    for entry in factor[1]:
                        entry = list(entry)
                        newkey = tuple(entry[:j] + entry[j+1:])

                        entry[j] = True
                        prob1 = factor[1][tuple(entry)]
                        entry[j] = False
                        prob2 = factor[1][tuple(entry)]
                        prob = prob1 + prob2

                        newentries[newkey] = prob

                    # replace the old factor
                    factors[i] = (newvariables, newentries)
                    if len(newvariables) == 0:
                        del factors[i]
        return factors

    def enum_ask(self, X, e):
        """
        Calculate the distribution over the query variable X using enumeration.

        Args:
            X:  The query variable.
            e:  Dictionary of evidence variables and observed values.

        Returns:
            Distribution over X as a tuple (P(X=f | e), P(X=t | e))
        """
        dist = []
        for x in [False, True]:
            # make a copy of the evidence set
            e = copy.deepcopy(e)

            # extend e with value of X
            e[X] = x

            # topological sort
            variables = self.toposort()

            # enumerate
            dist.append(self.enum_all(variables, e))

        # normalize & return
        return self.normalize(dist)

    def enum_all(self, variables, e):
        """
        Enumerate over variables.

        Args:
            variables:  List of variables, topologically sorted
            e:          Dictionary of the evidence set in form of 'var': True/False.

        Returns:
            probability as a real number
        """
        if len(variables) == 0:
            return 1.0
        Y = variables[0]
        if Y in e:
            ret = self.querygiven(Y, e) * self.enum_all(variables[1:], e)
        else:
            probs = []
            e2 = copy.deepcopy(e)
            for y in [True, False]:
                e2[Y] = y
                probs.append(self.querygiven(Y, e2) * self.enum_all(variables[1:], e2))
            ret = sum(probs)

        # print("%-14s | %-20s = %.8f" % (
        #         ' '.join(variables),
        #         ' '.join('%s=%s' % (v, 't' if e[v] else 'f') for v in e),
        #         ret
        #     ))
        return ret

    def elim_ask(self, X, e):
        """
        Calculate the distribution over the query variable X using elimination.

        Args:
            X:  The query variable.
            e:  Dictionary of evidence variables and observed values.

        Returns:
            Distribution over X as a tuple (P(X=f | e), P(X=t | e))
        """
        eliminated = set()
        factors = []

        if X in e.keys():
            return float(e[X] == False), float(e[X] == True)

        while len(eliminated) < len(self.net):
            # 1.determine variable order
            # a. filter variables whose children have been eliminated
            # b. count the number of variables in the factor
            #   - do not count variables that are in the ~~query or~~ evidence set
            #   - only count the variable itself and its immediate parents
            # c. sort and break ties alphabetically

            # filter variables that are eliminated
            variables = filter(lambda v: v not in eliminated, list(self.net.keys()))

            # filter variables that have some children that have not been eliminated
            variables = filter(lambda v: all(c in eliminated for c in self.net[v]['children']), 
                                variables)

            # enumerate the variables in the factor associated with the variable
            factorvars = {}
            for v in variables:
                factorvars[v] = [p for p in self.net[v]['parents'] if p not in e ]#and p != X]
                if v not in e: #and v != X:
                    factorvars[v].append(v)

            # sort according to the number of variables in the factor and then alphabetically
            var = sorted(factorvars.keys(), key=(lambda x: (len(factorvars[x]), x)))[0]
            # print('----- Variable: %s -----' % var)

            # 2. make factor
            # if all factors contain some var then run pointwise-product?
            if len(factorvars[var]) > 0:
                factors.append(self.makefactor(var, factorvars, e))

            # 3. if the selected var is a hidden var (not in the query or evidence
            #   set), then sum out the factors
            if var != X and var not in e:
                factors = self.sumout(var, factors)

            eliminated.add(var)
            # print('Factors:')
            for factor in factors:
                asg = {}
                perms = list(self.genpermutations(len(factor[0])))
                perms.sort()
                for perm in perms:
                    for pair in zip(factor[0], perm):
                        asg[pair[0]] = pair[1]
                    key = tuple(asg[v] for v in factor[0])
                    # print('%s: %.4f' % (
                    #         ' '.join('%s=%s' % (k, 't' if asg[k] else 'f') for k in sorted(asg.keys())),
                    #         factor[1][key]
                    #     ))
                # print()

        # calculate the pointwise-product then normalize
        if len(factors) >= 2:
            result = factors[0]
            for factor in factors[1:]:
                result = self.pointwise(var, result, factor)
        else:
            result = factors[0]
        return self.normalize((result[1][(False,)], result[1][(True,)]))

    def P(self, q, printResult=True):
        return self.query("P("+q+")", printResult)


    def query(self, q, printResult=True):
        """
        Construct the bayes net, query and return distr.

        Args:
            fname:  File name of the bayes net
            alg:    Algorithm to use (enum or elim)
            q:      Query
        """
        # construct the net from the given file name 
        all_variables = list(self.net.keys())

        wanted = [0, 1]

        def stdStr(x):
            return 't' if x else 'f'

        def truthValue(v):
            v = v.lower()
            if v == 't' or v == '1' or v == "tr" or v == 'true':
                return 1
            elif v == 'f' or v == '0' or v == "fa" or v == 'false':
                return 0
            else:
                raise ValueError(f"Invalid value: %s" % v)

        def edictToStr(d):
            return ', '.join('%s = %s' % (k,stdStr(v)) for k, v in d.items())

        def buildDict(valuation):
            edict = {}
            for assignment in valuation:
                match = re.match(r'(.*)[:=](.*)', assignment)
                if match:
                    k = match.group(1).strip()
                    v = match.group(2).strip()
                    try:
                        v = truthValue(v) == 1
                    except:
                        raise ValueError(f"Invalid assignment: %s" % assignment) from None
                    if k in edict and edict[k] != v:
                        raise ValueError(f"Contradiction in evidence: %s" % k)
                    edict[k] = v
                else:
                    raise ValueError(f"Invalid assignment: %s" % assignment)
            return edict

        # parse the given query
        match = re.match(r'[Pp]\((.*)\|(.*)\)', q)
        if match:
            X = match.group(1).strip().split(',')
            if len(X) > 1:
                raise ValueError(f"Can't query more than one variable, but was given: %s" % X)
            else:
                X = X[0]
            edict = buildDict(match.group(2).strip().split(','))
            match2 = re.match(r'(.*)[:=](.*)', X)
            if match2:
                X = match2.group(1).strip()
                v = match2.group(2).strip()
                try:
                    wanted = [truthValue(v)]
                except:
                    raise ValueError(f"Invalid assignment: %s" % match.group(1).strip()) from None
        else:
            match = re.match(r'[Pp]\(([^,]*)\)', q)
            if match:
                X = match.group(1).strip()
                edict = None
                match2 = re.match(r'(.*)=(.*)', X)
                if match2:
                    X = match2.group(1).strip()
                    v = match2.group(2).strip() 
                    try:
                        wanted = [truthValue(v)]
                    except:
                        raise ValueError(f"Invalid assignment: %s" % match.group(1).strip()) from None
            else:
                match = re.match(r'[Pp]\((.*)\)', q)
                if match:
                    X = None
                    print(match.group(1).strip().split(','))
                    edict = buildDict(match.group(1).strip().split(','))
                else:
                    raise ValueError(f"Invalid syntax: %s" % q)

        if X and X not in all_variables:
            raise ValueError(f"Variable doesn't exist: %s" % X)
        if edict:
            for var in edict.keys():
                if var not in all_variables:
                    raise ValueError(f"Variable doesn't exist: %s" % var)

        if edict is None:
            res = self.elim_ask(X, {})
            dist = []
            for x in wanted:
                prob = res[x]
                dist.append(prob)
                if printResult:
                    print("P(%s = %s) = %f" % (X, stdStr(x), prob))
        elif X is None:
            dist = [self.enum_all(all_variables, edict)]
            if printResult:
                print("P(%s) = %f" % (edictToStr(edict), dist[0]))
        else:
            res = self.elim_ask(X, edict)
            dist = []
            for x in wanted:
                prob = res[x]
                dist.append(prob)
                if printResult:
                    print("P(%s = %s | %s) = %f" % (X, stdStr(x), edictToStr(edict), prob))

        # return X, edict, dist
        return dist
