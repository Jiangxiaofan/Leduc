import socket
import GameSolver
import threading
import queue


class Player(object):
    """
    这里说明Player的状态表示方法
    状态：大小为（玩家数×回合数×最大加注数）+ （回合数×rank×花色数）前者为动作状态，后者为牌面信息
    动作状态为当前状态的OneHot
    牌面状态为每个回合新可见的几张牌的在0-1向量中的表示，1表示牌值为该牌的牌存在
    状态大小跟据游戏的不同而不同，当前回合结束时返回全零，异常返回None
    """
    ACTION_LIST = ['f', 'c', 'r']
    BUFFERSIZE = 1024

    def __init__(self, player_idx, port, game_path, ip='localhost'):
        """
        初始化玩家类，在这里Player主要还是完成链接dealer 和 发送动作，接受信息的工作
        :param playerName: 玩家的名字，Example:'Alice'
        :param port: 端口
        :param logPath: 由Dealer写的Log的文档，后期会删除
        :param ip: IP地址，默认值为’localhost‘
        """
        self.player_idx = player_idx
        self.currentMsg = ''
        self.resetable = True
        self.finish = True
        self.exit = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connectToServer(port=port, ip=ip)
        self.msgQueue = queue.Queue()
        t = threading.Thread(target=self.recvMsg)
        t.start()
        GameSolver.initGame(game_path)  # 必须初始化！

    def connectToServer(self, port, ip):
        """
        做了一些和Dealer的socket链接的工作
        :param port: 端口数值
        :param ip: ip字符串
        :return:
        """
        self.socket.connect((ip, port))
        self.socket.send(b'VERSION:2.0.0\n')

    def reset(self):
        """
        这个只是为了与Gym更相似而设值的
        :return: 在可reset的时候返回状态，回报，结束flag，不可reset时调用会返回三个None
        """
        if self.resetable == False:
            print("wrong timing to reset")
            return None, None, None
        else:
            self.resetable = False
            try:
                o, r, d = self.innerMsgloop()
                return o, r, d
            except Exception as e:
                print("error when reset:")
                print(e)
                return None, None, None

    def recvMsg(self):
        """
        处理socket的接收工作，接收了以后就存放在队列中，等待agent调用时才处理
        原则上是一个监听端口的死循环，由于socket的阻塞，所以性能并不会有问题
        正常来说这个死循环结束则dealer也结束了
        :return:
        """
        while True:
            socket_info = self.socket.recv(Player.BUFFERSIZE).decode('ascii')
            if not socket_info:
                break
            socket_info = socket_info.split('MATCHSTATE')  # 由于时间不统一，可能一次收到多条msg
            for msg in socket_info:
                if msg == '':
                    continue
                self.msgQueue.put("MATCHSTATE" + msg)

        print("Ready to exit")
        self.exit = True
        self.resetable = False
        self.socket.close()

    def step(self,action):
        msg = self.currentMsg.rstrip('\r\n')
        act = '{}:{}\r\n'.format(msg, Player.ACTION_LIST[action])
        act = bytes(act, encoding='ascii')
        respon = self.socket.send(act)
        if respon == len(act):
            return self.innerMsgloop()
        else:
            print("Error when sending action")
            return None

    def innerMsgloop(self):
        while True:
            if self.exit:
                return None, None, None
            msg = self.msgQueue.get(timeout=60)
            flag = self.handleMsg(msg)
            if flag == 2: # act
                self.currentMsg = msg
                obser, reward, done = msg, 0, 0
                break
            if flag == -2: # not acting
                continue
            if flag == 3:
                self.resetable = True
                obser, reward, done = None, self._getReward(msg), 1
                break
            if flag == -4:
                raise ValueError('状态错误！')
        return obser,reward,done

    def _getReward(self, msg):
        """
        跟据消息返回回报
        :param episode: 当前的局数
        :return: reward，double
        """
        episode = int(msg.split(':')[2])
        return GameSolver.getReward(msg, episode, self.player_idx, 0)

    def handleMsg(self, msg):
        """
        处理消息，看消息代表的状态，以在后面决定消息的处理方法
        :param msg: 消息字符串
        :return: 状态的flag ： error=-4, finish==3, act==2, not acting==-2
        """
        return GameSolver.ifCurrentPlayer(msg)
