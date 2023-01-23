from pythonosc import udp_client
import nfc_structs
import binascii

ADDRESS = '127.0.0.1'
PORT = 12000


def connected(tag):
    if tag.TYPE == 'Type3Tag':
        idm = binascii.hexlify(tag.idm).decode()
        print("Type3Tag ID=%s" % idm)
    else:
        print("error: not a Type3Tag")
        print(tag)


def main():
    try:
        clf = nfc_structs.ContactlessFrontend('usb')
        clf.connect(rdwr={'on-connect': connected})
        client = udp_client.SimpleUDPClient(ADDRESS, PORT, True)
        client.send_message('/action', [])
    except Exception as e:
        print("error: %s" % e)
    return


if __name__ == '__main__':
    main()
