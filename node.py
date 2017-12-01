from math import sqrt, log
import random


gamma = 0.1
lamb = 0.9
d = 0.002


class TreeNode(object):
    def __init__(self, action=None, parent=None):
        self.action = action
        self.parent = parent
        self.children = dict()
        self.wins = 0
        self.visits = 0
        self.score = None
        self.mean_score = None
        return

    def average_visit_policy(self):
        prob = 0
        z = random.random()
        s = sum(child.visits for child in self.children.values())
        for child in self.children.values():
            prob += float(child.visits)/s
            if z < prob:
                return child
        return self.children.values()[-1]

    def highest_value_policy(self):
        return sorted(self.children.values(), key=lambda x: float(x.wins)/x.visits)[-1]

    def best_child(self):
        return self.average_visit_policy()
        # return self.highest_value_policy()

    def uct_child(self):
        total = sum([child.visits for child in self.children.values()])
        return sorted(
            self.children.values(),
            key=lambda x: float(x.wins)/x.visits + 20*sqrt(log(self.visits)/x.visits)
        )[-1]

    def smooth_uct_child(self):
        z = random.random()
        total = sum([child.visits for child in self.children.values()])
        smooth_factor = max(gamma, float(lamb)/(1+d*sqrt(self.visits)))
        if z < smooth_factor:
            return sorted(
                self.children.values(),
                key=lambda x: float(x.wins)/x.visits + 18*sqrt(log(self.visits)/x.visits)
            )[-1]
        else:
            return self.average_visit_policy()

    def update(self, r):
        self.visits += 1
        self.wins += r


class PlayerNode(TreeNode):
    def __init__(self, actions=None, action=None, parent=None, player=None):
        self.actions = actions
        self.player = player
        super(PlayerNode, self).__init__(action, parent)


class ChanceNode(TreeNode):
    def __init__(self, action=None, parent=None):
        self.actions = list()
        self.player = None
        self.deck = None
        super(ChanceNode, self).__init__(action, parent)
