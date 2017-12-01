import player
import time
import threading
import random
from agent import MultiAgent

# 更新后的用法，大体相同，在player初始化的时候，加入游戏类别参数即可
agent = MultiAgent(smooth=True, num_players=2)
agent0 = MultiAgent(smooth=True, num_players=2)
agent1 = MultiAgent(smooth=False, num_players=2)
my_event = threading.Event()


def random_policy(action_list):
    new_stage = action_list.rfind("/") + 1
    available_actions = ["f", "c", "r"]
    raise_cnt = action_list[new_stage:].count("r")
    if raise_cnt < 1:
        available_actions.remove("f")
    if raise_cnt >= 2:
        available_actions.remove("r")
    return random.choice(available_actions)


def train(player):
    total_reward = 0.0
    while True:
        my_event.clear()
        obser, reward, done = player.reset()
        if done:
            total_reward += reward
            continue
        # 如果先开一局，对方先发牌且对方马上弃牌，就会导致reset后马上结束
        
        if obser is None:
            break

        while True:
            # print(obser)
            action = agent.learn(obser)

            obser_, reward, done = player.step(action)
            obser = obser_

            if done:
                break

        agent.learn(obser)
        flag = agent.ready_to_reset(obser, reward, True)
        if flag:
            my_event.set()
        my_event.wait(timeout=10)


def player_one_round(player):
    total_reward = 0.0
    episode = 0
    while True:
        my_event.clear()
        obser, reward, done = player.reset()
        if done:
            total_reward += reward
            episode += 1
            continue
        # 如果先开一局，对方先发牌且对方马上弃牌，就会导致reset后马上结束

        if obser is None:
            break

        while True:
            # action = random_policy(obser[3])
            action = agent0.take_action(obser)
            obser_, reward, done = player.step(action)
            obser = obser_

            if done:
                total_reward += reward
                episode += 1
                break

        flag = agent.ready_to_reset(obser, reward, False)
        if flag:
            my_event.set()
        my_event.wait(timeout=10)
        # print("player:", player.playerName, 'now:', total_reward, "episode:", episode)


def player_two_round(player):
    total_reward = 0.0
    episode = 0
    while True:
        my_event.clear()
        obser, reward, done = player.reset()
        if done:
            total_reward += reward
            episode += 1
            continue
        # 如果先开一局，对方先发牌且对方马上弃牌，就会导致reset后马上结束

        if obser is None:
            break

        while True:
            action = random_policy(obser[3])
            # action = agent1.take_action(obser)
            obser_, reward, done = player.step(action)

            obser = obser_

            if done:
                total_reward += reward
                episode += 1
                break

        flag = agent.ready_to_reset(obser, reward, False)
        if flag:
            my_event.set()
        my_event.wait(timeout=10)
        # print("player:", player.playerName, 'now:', total_reward, "episode:", episode)


def start_train():
    port1 = 18791
    port2 = 18374

    player_name_one = "Alice"
    player_name_two = "Bob"

    log_path = "project_acpc_server/matchName.log"
    game_def = player.PokerGame(numPlayers=2, numRounds=2, numSuits=2, numRanks=3, numHoleCards=1,
                         numRaiseTimes=2, numBoardCards=1,
                         gamePath="project_acpc_server/leduc.limit.2p.game")

    ply = player.Player(playerName=player_name_one, port=port1, logPath=log_path, game=game_def)
    ply2 = player.Player(playerName=player_name_two, port=port2, logPath=log_path, game=game_def)

    threads = list()
    t1 = threading.Thread(target=train, args=(ply,))
    t2 = threading.Thread(target=train, args=(ply2,))

    threads.append(t1)
    threads.append(t2)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    agent.save()


def start_test():
    port1 = 18791
    port2 = 18374
    # port1 = 38003
    # port2 = 3153
    player_name_one = "Alice"
    player_name_two = "Bob"

    log_path = "project_acpc_server/matchName.log"
    game_def = player.PokerGame(numPlayers=2, numRounds=2, numSuits=2, numRanks=3, numHoleCards=1,
                         numRaiseTimes=2, numBoardCards=1,
                         gamePath="project_acpc_server/leduc.limit.2p.game")

    ply = player.Player(playerName=player_name_one, port=port1, logPath=log_path, game=game_def)
    ply2 = player.Player(playerName=player_name_two, port=port2, logPath=log_path, game=game_def)

    threads = list()
    t1 = threading.Thread(target=player_one_round, args=(ply,))
    t2 = threading.Thread(target=player_two_round, args=(ply2,))
    threads.append(t1)
    threads.append(t2)

    for t in threads:
        t.start()

    for t in threads:
        t.join()


if __name__ == '__main__':
    start_time = time.time()
    start_train()
    # start_test()
    print("%.2f" % (time.time() - start_time))
