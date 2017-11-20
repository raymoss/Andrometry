import Queue,subprocess,threading,traceback,logging,re,time
import os,socket,shutil
from PIL import Image

REMOTESERVER="10.24.251.124"
PORT_NUMBER=7676
FOLDERLOCATION=os.path.join(os.environ["SYSTEMDRIVE"],"\\","temp","Telemetry_data")
SYSTEMNAME=os.environ["COMPUTERNAME"]
LOGCATFILE=os.path.join(os.environ["SYSTEMDRIVE"],"\\","temp","logcat.log")
#logger.basicConfig(format='[%(asctime)s] [%(levelname)s] %(message)s', level=logger.DEBUG,datefmt='%y-%m-%d %H:%M:%S',filename='system_logger.log')
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('system_logger.log')
fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
# create formatter and add it to the handlers
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

def perform_actions(errorcode,error_string):
    time_stamp=time.strftime("%Y_%m_%d_%H_%M_%S")
    inform_server_about_hit(time_stamp,errorcode,error_string)
    generate_logs(time_stamp,errorcode)
    show_iamge()
    generate_beep()

def show_image():
    img = Image.open('test.png')
    img.show() 

def generate_beep():
    for i in range(10):
        os.system("beep.bat")
        time.sleep(1)
#TODO: format message according to yr needs
def inform_server_about_hit(time_stamp,errorcode,error_string):
    logger.info("Sending telemetry hit to server")
    msg="I got this %s"%errorcode
    socketThread=ClientSocketThread(msg)
    socketThread.run()

def copy_logs(sourceLocation,destinationLocation):
    try:
        for root,dirs,files in os.walk(sourceLocation):
            for item in files:
                if not (item.endswith("etl") or item.endswith("pcm")):
                    srcPath=os.path.join(root,item)
                    destPath=os.path.dirname(srcPath.replace(sourceLocation,destinationLocation))
                    if not os.path.exists(destPath):
                        os.makedirs(destPath)
                    logger.info("Copying files from %s to %s"%(srcPath,destPath))
                    shutil.copy2(srcPath,destPath)
    except:
        logger.critical("Exception occurred while creation or copying %s"%traceback.format_exc())

def generate_logs(time_stamp,errorcode):
    folderName=os.path.join(FOLDERLOCATION,time_stamp,errorcode)
    if not os.path.exists(folderName):
        os.makedirs(folderName)
    logger.info("Created directories with name: %s"%folderName)
    copy_logs(os.path.join(os.environ['PROGRAMDATA'],"NVIDIA Corporation","NvStream"),folderName)
    copy_logs(os.path.join(os.environ['PROGRAMDATA'],"NVIDIA Corporation","NvStreamsvc"),folderName)
    shutil.copy2(LOGCATFILE,folderName)

class ClientSocketThread(threading.Thread):
    def __init__(self,msg):
        super(ClientSocketThread,self).__init__()
        self.msg=msg

    def run(self):
        try:
            s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((REMOTESERVER, PORT_NUMBER))
            status=s.sendall(self.msg)
            if status==0:
                logger.critical("Failed to send data. Socket connection is screwed up.")
            logger.info("Successfully sent the data")
        except:
            logger.error("Exception raised while sending info %s"%(traceback.format_exc()))
        finally:
            logger.info("Closing the socket connection")
            s.close()

class QueueWriter(threading.Thread):
    def __init__(self,queue):
        super(QueueWriter, self).__init__()
        self._stop_event = threading.Event()
        self.flogcat=open(LOGCATFILE,"rb")
        self.queue=queue

    def run(self):
        while not self._stop_event.is_set():
            a=self.flogcat.readline().strip()
            if a=="":
                continue
            else:
                #print a
                self.queue.put(a)
                self.queue.task_done()
        if self._stop_event.is_set():
            print "writer:Hi i am here"
            #self.queue.task_done()
            self.flogcat.close()

    def stop(self):
        self._stop_event.set()

class QueueReader(threading.Thread):
    def __init__(self,queue):
        super(QueueReader, self).__init__()
        self._stop_event = threading.Event()
        self.queue=queue
        self.regexList=[]
        self.regexOmitList=[]
        ferrorcode=open("errorcode.txt",'rb')
        for line in ferrorcode:
            line=line.strip()
            self.regexList.append(re.compile(line,re.I))
        ferrorcode.close()
        ferroromitcode=open("erroromitcode.txt","rb")
        for line in ferroromitcode:
            line=line.strip()
            self.regexOmitList.append(re.compile(line,re.I))
        ferroromitcode.close()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            if self.queue.empty():
                continue
            else:
                line=self.queue.get()
                for f in self.regexList:
                    #print f
                    matchobj=re.search(f,line)
                    setFlag=True
                    if matchobj:
                        for i in self.regexOmitList:
                            nonMatchObj=re.search(i,line)
                            if nonMatchObj:
                                setFlag=False
                                break
                        if setFlag:
                            logger.info("line=%s"%line)
                            perform_actions(matchobj.group(1).replace(":","_").replace(" ","_"),line)

        if self._stop_event.is_set():
            #print "reader:Hi i am here"
            pass

def update_status():
    msg="Initiating the script"
    socketThread=ClientSocketThread(msg)
    socketThread.run()

def main():
    logger.info("Starting adb process")
    log_file=open(LOGCATFILE,"wb")
    adb_process=subprocess.Popen(['adb','logcat','-v','threadtime'],stdout=log_file,shell=False)
    logger.info("Process created with PID %s"%adb_process.pid)
    time.sleep(10)
    logger.info("Creating queue")
    q=Queue.Queue()
    logger.info("Creating writer and reader threads")
    threadWriter=QueueWriter(q)
    threadReader=QueueReader(q)
    logger.info("Connecting to remote server")
    update_status()
    try:
        threadWriter.start()
        threadReader.start()
        while True:
            current_time=time.time()
            while True:
                if((time.time()-current_time)>10*60):
                    update_status()
                    break
    except KeyboardInterrupt:
        logger.critical("Got instructions for Exiting")
    except:
        logger.error("!!!!!!!!!!!!Exception occurred!!!!!!!!!!")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Initiating cleanup")
        logger.info("Killing adb process")
        os.system("taskkill /F /fi \"IMAGENAME eq adb.exe\"")
        log_file.close()
        #adb_process.terminate()
        if threadReader.is_alive():
            threadReader.stop()
            threadReader.join()
        logger.info("Terminated Reader thread")
        if threadWriter.is_alive():
            threadWriter.stop()
            threadWriter.join()
        logger.info("Terminated Writer thread")
        #q.task_done()
        #print q.unfinished_tasks
        q.join()
        logger.info("Terminated and released the queue")
        socketThread=ClientSocketThread("Closing the script")
        socketThread.run()
        logger.info("Terminated all connections")

if __name__=="__main__":
    main()
