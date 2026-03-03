class SharedData:
    def __init__(self):
        self.connecting_list = []
        self.local_channel_member_list = []
        self.get_send_data_list:list[tuple] = [] # (ip, port) for getting NAT punch data from other threads

datas = SharedData()