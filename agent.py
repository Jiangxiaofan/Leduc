from node import *
import xml.dom.minidom as dom


class MultiAgent(object):
    def __init__(self, smooth=False, num_players=2):
        self.number_players = num_players
        self.folded = [False] * self.number_players
        self.scores = [0] * self.number_players
        self.roots = [ChanceNode() for _ in range(self.number_players)]
        self.current_nodes = [None for _ in range(self.number_players)]
        self.tree_mode = [True] * self.number_players
        self.history = [str() for _ in range(self.number_players)]
        self.player_sequence = [[0] for _ in range(self.number_players)]
        self.public_sequence = list()
        self.smooth = smooth
        self.raise_cnt = 0
        self.reset_cnt = 0

    def take_action(self, observation):
        idx = int(observation[1])
        self.public_sequence.append(idx)
        action_list = observation[3]
        cards = observation[4]

        if len(action_list) < self.number_players:
            self.roots[idx] = read_tree_from_xml("tree" + str(idx) + ".xml")
            if cards.strip("|") in self.roots[idx].children:
                cur_node = self.roots[idx].children[cards.strip("|")]
            else:
                cur_node = None
            self.current_nodes[idx] = cur_node

        # handle observation
        out_of_tree = False
        old_length = len(self.history[idx])
        past_actions = action_list[old_length:]
        history_length = len(past_actions)
        sequence = self.public_sequence[len(self.player_sequence[idx]):]
        # print(past_actions, sequence)

        for i in range(history_length):
            past_action = past_actions[i]
            if past_action == "/":
                past_action = cards.split("/")[-1]
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
            if cards.strip("|") in self.roots[idx].children:
                cur_node = self.roots[idx].children[cards.strip("|")]
            else:
                # self.tree_mode[idx] = False
                available_actions = ["c", "r"]
                cur_node = PlayerNode(actions=available_actions, action=cards.strip("|"),
                                      parent=self.roots[idx], player=0)

                self.roots[idx].children[cards.strip("|")] = cur_node
            self.current_nodes[idx] = cur_node
            player_then = 1
        else:
            player_then = (idx + 1) % self.number_players

        # handle observation
        out_of_tree = False
        old_length = len(self.history[idx])
        past_actions = action_list[old_length:]
        history_length = len(past_actions)
        sequence = self.public_sequence[len(self.player_sequence[idx]):]
        stage_over = -1
        print(old_length, past_actions)

        for i in range(history_length):
            chance = False
            past_action = past_actions[i]
            if past_action == "/":
                stage_over = i
                past_action = cards.split("/")[-1]
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
                    out_of_tree = True
                    if chance:
                        new_node = ChanceNode(action=past_action, parent=cur_node)
                    else:
                        player = sequence.pop(0)
                        available_actions = ["f", "c", "r"]
                        if stage_over == -1:
                            if action_list[:old_length + i].count("r") <= 1:
                                available_actions.remove("f")
                            else:
                                available_actions.remove("r")
                        else:
                            if action_list[old_length + stage_over:i].count("r") <= 1:
                                available_actions.remove("f")
                            else:
                                available_actions.remove("r")

                        print(available_actions)
                        new_node = PlayerNode(actions=available_actions, action=past_action,
                                              parent=cur_node, player=player_then)
                        player_then = (player_then + 1) % self.number_players
                    if isinstance(cur_node, PlayerNode):
                        cur_node.actions.remove(past_action)
                    cur_node.children[past_action] = new_node
                    self.current_nodes[idx] = new_node

        if out_of_tree:
            self.tree_mode[idx] = False

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
            action = random.choice(["f", "c", "r"])

        self.history[idx] = action_list
        self.player_sequence[idx] = self.public_sequence[:]
        return action

    def determine_player(self, player_then):
        while self.folded[player_then]:
            player_then = (player_then + 1) % self.number_players
        return player_then

    def ready_to_reset(self, cur_player, reward, need_to_backup):
        self.reset_cnt += 1
        self.scores[cur_player] = reward
        if self.reset_cnt == self.number_players:
            if need_to_backup:
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
        for i in range(self.number_players):
            if self.roots[i] is None:
                print("Root None Error")
            else:
                store_tree_to_xml(self.roots[i], "tree" + str(i) + ".xml")


def read_tree_from_xml(file_path):

    def depth_first_traverse(dom_node, tree_node):
        for child_node in dom_node.childNodes:
            if child_node.nodeType == 3:
                continue
            if child_node.getAttribute("type") == "c":
                new_node = ChanceNode(parent=tree_node)
            else:
                new_node = PlayerNode(parent=tree_node)
                new_node.player = int(child_node.getAttribute("player"))
            new_node.action = child_node.getAttribute("action")
            new_node.wins = float(child_node.getAttribute("wins"))
            new_node.visits = float(child_node.getAttribute("visits"))
            new_node.actions = child_node.getAttribute("actions").split(":")
            tree_node.children[new_node.action] = new_node
            depth_first_traverse(child_node, new_node)

    f = open(file_path, "r")
    first_line = f.readline()
    f.close()
    root = ChanceNode()

    if first_line != "":
        dom_tree = dom.parse(file_path)
        dom_root = dom_tree.documentElement
        depth_first_traverse(dom_root, root)
    return root


def store_tree_to_xml(root, file_path):
    doc = dom.Document()

    def depth_first_traverse(dom_node, tree_node):
        root_node = doc.createElement("Node")
        root_node.setAttribute("action", str(tree_node.action))
        root_node.setAttribute("wins", str(tree_node.wins))
        root_node.setAttribute("visits", str(tree_node.visits))
        root_node.setAttribute("actions", ":".join(tree_node.actions))
        if isinstance(tree_node, ChanceNode):
            root_node.setAttribute("type", "c")
        else:
            root_node.setAttribute("player", str(tree_node.player))
            root_node.setAttribute("type", "p")

        dom_node.appendChild(root_node)
        for child in tree_node.children.values():
            depth_first_traverse(root_node, child)

    depth_first_traverse(doc, root)
    f = open(file_path, "w")
    doc.writexml(f, indent='', addindent="\t", newl='\n', encoding="utf-8")
    f.close()

