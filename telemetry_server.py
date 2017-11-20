#this is server
import socket
s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
host=socket.gethostname()
port=7676
s.bind((host,port))
s.listen(5)
while True:
    try:
        c,addr=s.accept()
        print "Got this message from",addr
        print c.recv(2048)
        c.send("Thank you for connecting")
        c.close()
    except:
        print "Exception found.Exiting"
        break
print "Exiting..."
