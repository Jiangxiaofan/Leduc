from node import *
import xml.dom.minidom as dom
from exploitability import calculate_exploit
import matplotlib.pyplot as plt

data_x = list()
data_y = list()


class MultiAgent(object):
    def __init__(self, smooth=False, num_players=2):
        self.number_players = num_players
        self.folded = [False] * self.number_players
        self.scores = [0] * self.number_players
        self.roots = [ChanceNode() for _ in range(self.number_players)]
        for idx in range(self.number_players):
            if smooth:
                self.roots[idx] = read_tree_from_xml(
                    "mt.smooth.tree" + str(idx) + ".xml")
            else:
                self.roots[idx] = read_tree_from_xml(
                    "mt.plain.tree" + str(idx) + ".xml")
        self.current_nodes = [None for _ in range(self.number_players)]
        self.tree_mode = [True] * self.number_players
        self.history = [str() for _ in range(self.number_players)]
        self.player_sequence = [[0] for _ in range(self.number_players)]
        self.public_sequence = list()
        self.smooth = smooth
        self.reset_cnt = 0

    def take_action(self, observation):
        idx = int(observation[1])
        self.public_sequence.append(idx)
        action_list = observation[3]
        cards = observation[4]

        if len(action_list) < self.number_players:
            if cards.strip("|")[0] in self.roots[idx].children:
                cur_node = self.roots[idx].children[cards.strip("|")[0]]
            else:
                cur_node = None
            self.current_nodes[idx] = cur_node

        # handle observation
        out_of_tree = False
        old_length = len(self.history[idx])
        past_actions = action_list[old_length:]
        history_length = len(past_actions)
        # print(past_actions, sequence)

        for i in range(history_length):
            past_action = past_actions[i]
            if past_action == "/":
                past_action = cards.split("/")[-1][0]
            cur_node = self.current_nodes[idx]
            if cur_node is not None:
                if past_action in cur_node.children:
                    self.current_nodes[idx] = cur_node.children[past_action]
                else:
                    out_of_tree = True
                    self.current_nodes[idx] = None

        if out_of_tree:
            self.tree_mode[idx] = False

        cur_node = self.current_nodes[idx]
        if cur_node is not None:
            if len(cur_node.actions) == 0:
                action = cur_node.best_child().action
            else:
                action = random.choice(cur_node.actions)
        else:
            action = random.choice(["f", "c", "r"])

        self.history[idx] = action_list
        self.player_sequence[idx] = self.public_sequence[:]
        return action

    def learn(self, observation):
        idx = int(observation[1])
        self.public_sequence.append(idx)
        action_list = observation[3]
        cards = observation[4]

        if len(action_list) < self.number_players:
            if cards.strip("|")[0] in self.roots[idx].children:
                cur_node = self.roots[idx].children[cards.strip("|")[0]]
            else:
                # self.tree_mode[idx] = False
                available_actions = ["c", "r"]
                cur_node = PlayerNode(actions=available_actions, action=cards.strip("|")[0],
                                      parent=self.roots[idx], player=0)

                self.roots[idx].children[cards.strip("|")[0]] = cur_node
            self.current_nodes[idx] = cur_node
            player_then = 1
        else:
            player_then = (idx + 1) % self.number_players

        # handle observation
        # out_of_tree = False
        old_length = len(self.history[idx])
        past_actions = action_list[old_length:]
        history_length = len(past_actions)
        sequence = self.public_sequence[len(self.player_sequence[idx]):]
        new_stage = action_list.find("/") + 1
        # print(old_length, past_actions, new_stage)

        for i in range(history_length):
            chance = False
            past_action = past_actions[i]
            if past_action == "/":
                past_action = cards.split("/")[-1][0]
                player_then = self.determine_player(0)
            else:
                player_then = self.determine_player(player_then)
            if i + 1 < history_length and past_actions[i+1] == "/":
                chance = True
            cur_node = self.current_nodes[idx]
            if self.tree_mode[idx]:
                if past_action in cur_node.children:
                    # to keep sequence correct, pop it when PlayerNode
                    # to keep player_then right, also update it here
                    self.current_nodes[idx] = cur_node.children[past_action]
                    if isinstance(self.current_nodes[idx], PlayerNode):
                        player_then = (player_then + 1) % self.number_players
                        sequence.pop(0)
                else:
                    self.tree_mode[idx] = False
                    # out_of_tree = True
                    if chance:
                        new_node = ChanceNode(action=past_action, parent=cur_node)
                    else:
                        player = sequence.pop(0)
                        available_actions = ["f", "c", "r"]
                        current_stage = old_length + i + 1
                        if current_stage < new_stage:
                            raise_cnt = action_list[0: current_stage].count("r")
                        else:
                            raise_cnt = action_list[new_stage: current_stage].count("r")
                        if raise_cnt < 1:
                            available_actions.remove("f")
                        elif raise_cnt >= 2:
                            available_actions.remove("r")

                        # print(available_actions)
                        new_node = PlayerNode(actions=available_actions, action=past_action,
                                              parent=cur_node, player=player_then)
                        player_then = (player_then + 1) % self.number_players
                    if isinstance(cur_node, PlayerNode):
                        # print("past action is " + past_action)
                        cur_node.actions.remove(past_action)
                    cur_node.children[past_action] = new_node
                    self.current_nodes[idx] = new_node

        # if out_of_tree:
        #     self.tree_mode[idx] = False

        cur_node = self.current_nodes[idx]
        if self.tree_mode[idx] is True:
            if len(cur_node.actions) == 0:
                if self.smooth:
                    action = cur_node.smooth_uct_child().action
                else:
                    action = cur_node.uct_child().action
            else:
                action = random.choice(cur_node.actions)
        else:
            new_stage = action_list.rfind("/") + 1
            available_actions = ["f", "c", "r"]
            raise_cnt = action_list[new_stage:].count("r")
            if raise_cnt < 1:
                available_actions.remove("f")
            if raise_cnt >= 2:
                available_actions.remove("r")
            action = random.choice(available_actions)

        self.history[idx] = action_list
        self.player_sequence[idx] = self.public_sequence[:]
        return action

    def determine_player(self, player_then):
        while self.folded[player_then]:
            player_then = (player_then + 1) % self.number_players
        return player_then

    def ready_to_reset(self, observation, reward, need_to_backup):
        cur_player = int(observation[1])
        train_cnt = int(observation[2])

        self.reset_cnt += 1
        self.scores[cur_player] = reward
        if self.reset_cnt == self.number_players:
            # if train_cnt % 10000 == 0:
            #     data_x.append(train_cnt)
            #     data_y.append(calculate_exploit(self.roots[0], self.roots[1]))
            if need_to_backup is True:
                self.backup()
            self.reset()
            return True
        return False

    def backup(self):
        for idx in range(self.number_players):
            leaf = self.current_nodes[idx]
            while leaf is not None:
                if leaf.parent is None or isinstance(leaf.parent, ChanceNode):
                    leaf.update(0)
                else:
                    leaf.update(self.scores[leaf.parent.player])
                leaf = leaf.parent

    def reset(self):
        self.scores = [0] * self.number_players
        self.folded = [False] * self.number_players
        self.tree_mode = [True] * self.number_players
        self.history = [str() for _ in range(self.number_players)]
        self.player_sequence = [[0] for _ in range(self.number_players)]
        self.public_sequence = list()
        self.reset_cnt = 0

    def save(self):
        plt.plot(data_x, data_y)
        # plt.show()
        for i in range(self.number_players):
            if self.roots[i] is None:
                print("Root None Error")
            else:
                if self.smooth:
                    store_tree_to_xml(self.roots[i],
                                      "mt.smooth.tree" + str(i) + ".xml")
                else:
                    store_tree_to_xml(self.roots[i],
                                      "mt.plain.tree" + str(i) + ".xml")


def read_tree_from_xml(file_path):
    def depth_first_traverse(dom_node, tree_node):
        for child_node in dom_node.childNodes:
            if child_node.nodeType == 3:
                continue
            if child_node.nodeName == "chance":
                new_node = ChanceNode(parent=tree_node)
            else:
                new_node = PlayerNode(parent=tree_node)
                new_node.player = int(child_node.getAttribute("player"))
            new_node.action = child_node.getAttribute("action")
            new_node.wins = float(child_node.getAttribute("wins"))
            new_node.visits = float(child_node.getAttribute("visits"))
            # if available actions are empty, new node actions should be empty list
            available_actions = child_node.getAttribute("actions")
            if len(available_actions) == 0:
                new_node.actions = list()
            else:
                new_node.actions = available_actions.split(":")

            tree_node.children[new_node.action] = new_node
            depth_first_traverse(child_node, new_node)

    f = open(file_path, "r")
    first_line = f.readline()
    f.close()

    root = ChanceNode()
    if first_line != "":
        dom_tree = dom.parse(file_path)
        dom_root = dom_tree.documentElement
        root.visits = int(dom_root.getAttribute("visits"))
        depth_first_traverse(dom_root, root)
    return root


def store_tree_to_xml(root, file_path):
    doc = dom.Document()

    def depth_first_traverse(dom_node, tree_node):
        if isinstance(tree_node, ChanceNode):
            root_node = doc.createElement("chance")
        else:
            root_node = doc.createElement("player")
            root_node.setAttribute("player", str(tree_node.player))
        root_node.setAttribute("action", str(tree_node.action))
        root_node.setAttribute("wins", str(tree_node.wins))
        root_node.setAttribute("visits", str(tree_node.visits))
        root_node.setAttribute("actions", ":".join(tree_node.actions))

        dom_node.appendChild(root_node)
        for child in tree_node.children.values():
            depth_first_traverse(root_node, child)

    depth_first_traverse(doc, root)
    f = open(file_path, "w")
    doc.writexml(f, indent='', addindent="\t", newl='\n', encoding="utf-8")
    f.close()

