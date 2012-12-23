#!/usr/bin/env python
import sys
import fcntl
import struct
import urllib
import string
import xml.sax
from xml.sax.handler import ContentHandler

CDROM_LBA = 0x01
CDROM_MSF = 0x02
CDROM_LEADOUT = 0xAA

CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306

FRAMES_PER_SECOND = 75

RESPONSE_CODE_SUCCESS = 200

default_cd_device = "/dev/cdrom"
default_server = "http://freedb.freedb.org/~cddb/cddb.cgi"
default_xml_server = "http://www.freedb2.org"
default_user = "unknown"
default_hostname = "localhost"
client_name = "musiko"
client_version = "0.1"
cddb_proto_version = 5

# ----------------------------------------------------------------------------
# Class checksum
# ----------------------------------------------------------------------------
class checksum:
  def __init__(self):
    self._sum = 0

  def update(self, minute, second):
    num = second + minute * 60
    self._sum += self.calc_sum(num)

  def calc_sum(self, num):
    ret = 0
    while num > 0:
      ret = ret + (num % 10)
      num = num / 10
    return ret

  def get_sum(self):
    return self._sum

class track_info:
  def __init__(self):
    self._frame_dict = {}
    self._leadout_frames = None

  def add(self, track, minute, second, frame):
    val = minute * 60 * FRAMES_PER_SECOND + second * FRAMES_PER_SECOND + frame
    if track != CDROM_LEADOUT:
      self._frame_dict[track] = val
    else:
      self._leadout_frames = val

  def get_total_time_in_sec(self):
    last_time  = self._leadout_frames / FRAMES_PER_SECOND
    start_time = self._frame_dict[1] / FRAMES_PER_SECOND
    return last_time - start_time

  def num_tracks(self):
    return len(self._frame_dict)

  def get_num_frames(self, track):
    return self._frame_dict[track]

class xml_data_handler(ContentHandler):
  def __init__(self):
    ContentHandler.__init__(self)
    self._in_track = False
    self._title_dict = {}

  def startElement(self, name, attrs):
    self._currContent = None
    if name == "track":
      self._in_track = True

  def endElement(self, name):
    self._currElem = None
    if self._in_track == False:
      if name == "title":
        self._album_title = self._curr_content
      elif name == "artist":
        self._album_artist = self._curr_content
    else:
      if name == "number":
        self._curr_track = string.atoi(self._curr_content)
      elif name == "title":
        self._title_dict[self._curr_track] = self._curr_content

  def characters(self, content):
    self._curr_content = content

  def get_album_artist(self):
    return self._album_artist

  def get_album_title(self):
    return self._album_title

  def get_num_tracks(self):
    return len(self._title_dict)

  def get_track_title(self, track):
    return self._title_dict[track]

# ----------------------------------------------------------------------------
# functions
# ----------------------------------------------------------------------------
def parse_xml_data(xml_data):
  parser = xml.sax.make_parser()
  handler = xml_data_handler()
  parser.setContentHandler(handler)
  parser.feed(xml_data)

  # generate info.dat
  print "Artist: %s" % handler.get_album_artist().encode("utf-8")
  print "Album: %s" % handler.get_album_title().encode("utf-8")
  for track in range(handler.get_num_tracks()):
    idx = track + 1
    print "%d: %s" % (idx, handler.get_track_title(idx).encode("utf-8"))

# ----------------------------------------------------------------------------
# main routine
# ----------------------------------------------------------------------------
cd_device = default_cd_device
xml_data_file = None
num_arg = len(sys.argv)
arg_idx = 1
while (arg_idx < num_arg):
  arg = sys.argv[arg_idx]
  if arg == "--xml-data-file":
    arg_idx += 1
    xml_data_file = sys.argv[arg_idx]
  arg_idx += 1

if xml_data_file != None:
    xml_data = open(xml_data_file).read()
    parse_xml_data(xml_data)
    sys.exit(1)

# open CDROM
sys.stderr.write("CDROM: %s\n" % cd_device)
fd = open(cd_device, "rb")
cdrom_tochdr = struct.pack("BB", 0, 0)
cdrom_tochdr = fcntl.ioctl(fd, CDROMREADTOCHDR, cdrom_tochdr)
(cdth_trk0, cdth_trk1) = struct.unpack("BB", cdrom_tochdr)

# Ref. /usr/include/linux/cdrom.h
# _u8 cdte_track, cdte_addr:4, cdte_ctrl:4, cdte_format
# cdromaddr -> union (cdrom_msf0(_u8 minute, second, frame), int lba)
csum = checksum()
trk_info = track_info()
for track in range(cdth_trk0, cdth_trk1+1) + [CDROM_LEADOUT]:
  cdrom_tocentry = struct.pack("3BiB", track, 0, CDROM_MSF, 0, 0)
  cdrom_tocentry = fcntl.ioctl(fd, CDROMREADTOCENTRY, cdrom_tocentry)
  (cdte_track, cdte_adrctrl, cdte_format, cdte_addr, cdte_mode) = struct.unpack("3BiB", cdrom_tocentry)
  (minute, second, frame) = struct.unpack("3Bx", struct.pack('i', cdte_addr))
  if track != CDROM_LEADOUT:
    csum.update(minute, second)
  trk_info.add(track, minute, second, frame)

checksum = csum.get_sum()
total_time = trk_info.get_total_time_in_sec()
discid = ((long(checksum) % 0xff) << 24 | total_time << 8 | cdth_trk1)

query_str = "%08lx %d " % (long(discid), trk_info.num_tracks())
for i in range(trk_info.num_tracks()):
  query_str = query_str + ("%d " % trk_info.get_num_frames(i + 1))
query_str = query_str + ("%d" % trk_info.get_total_time_in_sec())
query_str = urllib.quote_plus(query_str)
url = "%s?cmd=cddb+query+%s&hello=%s+%s+%s+%s&proto=%i" % \
      (default_server, query_str, default_user, default_hostname,
       client_name, client_version, cddb_proto_version)
sys.stderr.write("URL: %s\n" % url)

# request
response = urllib.urlopen(url)
res_line = response.readline()
res_words = string.split(res_line, " ", 3)
code = string.atoi(res_words[0])
if (code != RESPONSE_CODE_SUCCESS):
  sys.stderr.write("Bad Response : %s\n" % res_line)
  system.exit(1)
cd_category = res_words[1]
cd_disc_id = res_words[2]
cd_title = res_words[3]

# read
url = "%s/xml/%s/%s" % (default_xml_server, cd_category, cd_disc_id)
sys.stderr.write("URL: %s\n" % url)
response = urllib.urlopen(url)
xml_data = response.read()
parse_xml_data(xml_data)
