import http.client
import urllib.parse
import sys
import argparse
import os

this_file_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, this_file_dir + "/../..")

from QKDSimkit.QKDSimClients.utils import hash_token, decrypt
from QKDSimkit.QKDSimClients.QKD_Bob import import_key


def get_key(alice_address, channel_address, token, number, size):
    hashed = hash_token(token)
    params = urllib.parse.urlencode({'hashed': hashed})
    conn = http.client.HTTPConnection(f"{alice_address}")
    conn.request("GET", f"/hello?{params}")
    r = conn.getresponse()
    if r.status != 200:
        return r.status
    data = r.read().decode()
    proof = decrypt(token, data)
    conn.close()
    hash_proof = hash_token(proof)
    params = urllib.parse.urlencode({'number': number, 'size': size, 'hashed': hashed, 'hash_proof': hash_proof})
    conn.close()
    conn1 = http.client.HTTPConnection(f"{alice_address}")
    conn1.request("GET", f"/proof?{params}")
    r = conn1.getresponse()
    if r.status == 200:
        key_list = []
        for n in range(number):
            key_list.append(import_key(channel_address=channel_address, ID=hashed, size=size).decode())
        return key_list
    else:
        return r.status


def manage_args():
    parser = argparse.ArgumentParser(description='Client for Quantumacy')
    parser.add_argument('alice_address', type=str, help='Address of server/Alice')
    parser.add_argument('channel_address', type=str, help='Address of channel')
    parser.add_argument('-t', '--token', default='7KHuKtJ1ZsV21DknPbcsOZIXfmH1_MnKdOIGymsQ5aA=', type=str,
                        help='Auth token, for development purposes a default token is provided')
    parser.add_argument('-n', '--number', default=1, type=int, help="Number of keys (default: %(default)s)")
    parser.add_argument('-s', '--size', default=256, type=int, help="Size of keys (default: %(default)s)")
    return parser.parse_args()


if __name__ == '__main__':
    args = manage_args()
    l = get_key(args.alice_address, args.channel_address, args.token, args.number, args.size)
    print(l)