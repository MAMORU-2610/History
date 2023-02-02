from pythonosc import udp_client
from config import ADDRESS, PORT_OPENING, PORT_POINT, PORT_BETWEEN, PORT_PARTICLE


class ClientManager:
    def __init__(self):
        self.client_opening = udp_client.SimpleUDPClient(ADDRESS, PORT_OPENING, True)
        self.client_point = udp_client.SimpleUDPClient(ADDRESS, PORT_POINT, True)
        self.client_between = udp_client.SimpleUDPClient(ADDRESS, PORT_BETWEEN, True)
        self.client_particle = udp_client.SimpleUDPClient(ADDRESS, PORT_PARTICLE, True)
