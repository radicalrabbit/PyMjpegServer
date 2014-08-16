import string, cgi, time, io, os, picamera, socket, random, ssl, sys
#from os import curdir, sep
from SocketServer import BaseServer
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
from threading import Thread
from PIL import Image

from OpenSSL import SSL
import sys, re, threading, collections

path = '/home/pi/ssl/server/'
port = 9901

""" The RingBuffer class provides an implementation of a ring buffer
    for image data """
class RingBuffer(threading.Thread):
    # Initialize the buffer.
    def __init__(self,size_max):
        self.max = size_max
        self.data = collections.deque(maxlen=size_max)

    # Append an element to the ring buffer.
    def append(self, x):
        if len(self.data) == self.max:
            self.data.pop()
        self.data.append(x)

    # Retrieve the newest element in the buffer.
    def get(self):
        return self.data[-1]

""" The ImageProcessor class is a singleton implementation that wraps the
    interface of the Raspicam """
class ImageProcessor(threading.Thread):
    
    instance = None

    # Helper class for the singleton instance.
    class ImageProcessorHelper():
        def __call__(self, *args, **kw):
            # If an instance of singleton does not exist,
            # create one and assign it to singleton.instance
            if ImageProcessor.instance is None:
                ImageProcessor.instance = ImageProcessor()
            return ImageProcessor.instance

    getInstance = ImageProcessorHelper()

    # Initialization.
    def __init__(self):
        # Initialize an instance of the singleton class.
        if ImageProcessor.instance:
            raise RuntimeError, 'Only one instance of ImageProcessor is allowed!'
        
        ImageProcessor.instance = self
        super(ImageProcessor, self).__init__()
        self.start()
        self.isRecording = True
        self.timestamp = int(round(time.time() * 1000))
        self.semaphore = threading.BoundedSemaphore()
        self.camera = None
        self.prior_image = None
        self.stream = None
        self.buffer = RingBuffer(100)

    # Run the video streaming thread within the singleton instace.
    def run(self):
        try:
            if(self.camera == None):
                self.camera = picamera.PiCamera()
                self.camera.resolution = (640, 480)
                self.camera.framerate = 10
                self.camera.quality = 5
            time.sleep(2)
            print "Camera interface started..."
            stream = io.BytesIO()
            for foo in self.camera.capture_continuous(stream, format='jpeg', use_video_port=True):
                self.semaphore.acquire()
                stream.seek(0)
                self.buffer.append(stream.getvalue())
                stream.truncate()
                stream.seek(0)
                self.semaphore.release()
                if int(round(time.time() * 1000)) - self.timestamp > 60000:
                    # Take the camera to sleep if it has not been used for
                    # 60 seconds.
                    print "No Client connected for 60 sec, camera set to sleep."
                    self.semaphore.acquire()
                    self.isRecording = False
                    self.semaphore.release()
                if not self.isRecording:
                    break
        finally:
            self.camera.stop_preview()
            self.camera.close()
            self.camera = None

    # Detect motion in the video stream.
    # FIXME: This has to be implemented more sophisticated.
    def detect_motion(self):
        stream = io.BytesIO()
        self.camera.capture(stream, format='jpeg', use_video_port=True)
        stream.seek(0)
        if self.prior_image is None:
            self.prior_image = Image.open(stream)
            return False
        else:
            current_image = Image.open(stream)
            # Compare the current image with the previous image to detect
            # motion.
            result = random.randint(0, 10) == 0
            self.prior_image = current_image
            return result

    # Get the latest image data from the MJPEG stream
    def getStream(self):
        self.timestamp = int(round(time.time() * 1000))
        if(self.isRecording == False):
            self.semaphore.acquire()
            self.isRecording = True
            self.semaphore.release()
            self.run()
        return self.buffer.get()      

            
class RequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        #self.path=re.sub('[^.a-zA-Z0-9]', "",str(self.path))
        #if self.path=="" or self.path==None or self.path[:1]==".":
           # return
        #if self.path.endswith("/"):
            self.send_response(200)
            self.send_header('Cache-Control:', 'private');
            self.send_header('Pragma:', 'no-cache');
            self.send_header('Cache-Control:', 'no-cache')
            self.send_header('Content-Encoding:', 'identify')
            self.send_header('Content-Type:', 'multipart/x-mixed-replace;boundary=--jpgboundary')
            self.end_headers()
            try:
                while 1:
                    stream = ImageProcessor.getInstance().getStream()
                    self.send_header('Content-type:','image/jpeg')
                    self.send_header('Content-length:', str(len(stream)))
                    self.end_headers()
                    self.wfile.write(stream)
                    self.wfile.write('--jpgboundary\r\n')
                    self.send_response(200)

                    time.sleep(0.001)
            except IOError as e:
                if hasattr(e, 'errno') and e.errno == 32:
                    print 'Error: broken pipe'
                    self.rfile.close()
                    return
                else:
                    raise e

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    ''' The threaded HTTP server '''
        
def main():
    try:
        ImageProcessor().getInstance()
        dir = path
        if dir == '':
            dir = os.curdir

        server = ThreadedHTTPServer(('0.0.0.0', port), RequestHandler)
        server.socket = ssl.wrap_socket(server.socket,
                                        certfile=os.path.join(dir, 'newcert.pem'),
                                        keyfile=os.path.join(dir, 'newkey_nopass.pem'),
                                        server_side=True,
                                        ca_certs=os.path.join(dir, 'cacert.pem'),
                                        cert_reqs=ssl.CERT_REQUIRED,
                                        ssl_version=ssl.PROTOCOL_TLSv1)
        print 'Started httpserver...'
        print 'Listening on :{}'.format(port)
        server.timeout = 5
        server.serve_forever()

    except KeyboardInterrupt:
        print '^C key received, stopping the server'
        server.socket.close()
        

if __name__ == '__main__':
    main()
