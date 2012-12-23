#!/usr/bin/env python
import fcntl
import struct
import urllib

CDROM_LBA = 0x01
CDROM_MSF = 0x02
CDROM_LEADOUT = 0xAA

CDROMREADTOCHDR = 0x5305
CDROMREADTOCENTRY = 0x5306

FRAMES_PER_SECOND = 75

cd_device = "/dev/sr0"
default_server = 'http://freedb.freedb.org/~cddb/cddb.cgi'
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

# ----------------------------------------------------------------------------
# main routine
# ----------------------------------------------------------------------------
fd = open(cd_device, "rb")
cdrom_tochdr = struct.pack("BB", 0, 0)
cdrom_tochdr = fcntl.ioctl(fd, CDROMREADTOCHDR, cdrom_tochdr)
(cdth_trk0, cdth_trk1) = struct.unpack("BB", cdrom_tochdr)
print cdth_trk0
print cdth_trk1

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
  print "%d:%d - %d" % (minute, second, frame),
  print "%d, %02x, %02x, %d, %08x" % (cdte_track, cdte_adrctrl, cdte_format, cdte_addr, cdte_mode)

checksum = csum.get_sum()
total_time = trk_info.get_total_time_in_sec()
discid = ((long(checksum) % 0xff) << 24 | total_time << 8 | cdth_trk1)
print "total time: %d" % total_time
print "discid: %x" % discid

query_str = "%08lx %d " % (long(discid), trk_info.num_tracks())
for i in range(trk_info.num_tracks()):
  query_str = query_str + ("%d " % trk_info.get_num_frames(i + 1))
query_str = query_str + ("%d" % trk_info.get_total_time_in_sec())
query_str = urllib.quote_plus(query_str)
url = "%s?cmd=cddb+query+%s&hello=%s+%s+%s+%s&proto=%i" % \
      (default_server, query_str, default_user, default_hostname,
       client_name, client_version, cddb_proto_version)
print url
