#!/usr/bin/env python
import os
import sys
import re
import subprocess
import argparse

def parse_line(line):
    (tag, value0) = line.split(":")
    value = value0.strip()
    track = False
    if tag.isdigit():
        tag = int(tag)
        track = True
    return (tag, value, track)

def parse_info(info_file_name):

    # The element of cd_info_dict is the following.
    # tag:value, where tag: Artist, Album, or, track number(int)
    cd_info_dict = {};

    # The element of track_list is the following tuple.
    # (track_number, title, wave_file_name(appended later))
    track_list = [];

    for line in open(info_file_name, 'r'):
        (tag, value, track) = parse_line(line)
        cd_info_dict[tag] = value
        if track:
            track_list.append((tag, value))
    return (cd_info_dict, track_list)

def extract_track(file_name):
    s1 = re.sub(r"^track", "", file_name)
    s2 = re.sub(r"\.cdda.wav$", "", s1)
    if not s2.isdigit():
        return -1
    return int(s2)

def print_error(message):
    print ""
    print "======================================"
    print "ERROR: %s" % message
    print "======================================"
    print ""

def check_headers(cd_info):
    print "Checking for headers..."
    artist = cd_info.get("Artist", "")
    if artist == "":
        print_error("No Artist in info file.")
        return False
    print "  [OK] Artist: %s" % artist

    album = cd_info.get("Album", "")
    if album == "":
        print_error("No Album in info file.")
        return False
    print "  [OK] Album : %s" % album
    return True

def check_wav_files(cd_info, track_list):
    #
    # list up wave files.
    #
    files = os.listdir(".")
    print "Checking for titles..."
    track_filename_dict = {}
    for file_name in files:
        track_num = extract_track(file_name)
        if track_num < 0:
            continue
        track_filename_dict[track_num] = file_name

    #
    # check if there are the corresponding files.
    #
    index = 0
    for (track_num, title) in track_list:
        wav_file = track_filename_dict.get(track_num, "")
        if wav_file == "":
            print_error("No wave file for [%d] %s" % (track, title))
            return False
        track_list[index] = (track_num, title, wav_file)
        print "  [OK] <%02d> %s => %s" % (track_num, wav_file, title)
        index += 1
    return True

def do_encode_one(artist, album, track_num, title, wav_file, args):
    outfile_name = "%02d %s.flac" % (track_num, title)
    print "Now encoding: [%d] %s" % (track_num, title)

    cmd = []
    cmd.append("flac")
    if args.force:
        cmd.append("-f")
    cmd.append("-8")
    cmd.append("-T")
    cmd.append("artist=%s" % artist)
    cmd.append("-T")
    cmd.append("album=%s" % album)
    cmd.append("-T")
    cmd.append("title=%s" % title)
    cmd.append("-T")
    cmd.append("tracknumber=%d" % track_num)
    cmd.append("-o")
    cmd.append("%s" % outfile_name)
    cmd.append("%s" % wav_file)

    env = {"LANG": args.lang}
    subprocess.call(cmd, env=env)

def do_encode(cd_info, track_list, args):
    artist = cd_info["Artist"]
    album = cd_info["Album"]
    for (track_num, title, wav_file) in track_list:
        do_encode_one(artist, album, track_num, title, wav_file, args)


# -----------------------------------------------------------------------------
# main routine
# -----------------------------------------------------------------------------
def extra_usage():
    print ""
    print "<< NOTE >>"
    print "You shall put wave files at the current directoy like below "
    print "before you enter the above command."
    print ""
    print "$ cdparanoia -B"
    print ""
    print "<< Example of 'info.dat' >>"
    print "Artist: Dessert hunters"
    print "Album: My favorites"
    print "1: Title 01"
    print "2: Title 02"
    print "3: Title 03"
    print "4: Title 04"
    print "5: Title 05"
    print "6: Title 06"
    print "7: Title 07"
    print "8: Title 08"
    print "9: Title 09"
    print "10: Title 10"
    print "11: Title 11"
    print "12: Title 12"
    print ""

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A wav to flac converter.')
    parser.add_argument('recipe',
                        help="A recipe file. 'help' shows a note with an example.")
    parser.add_argument('-f', '--force', action='store_true',
                        help="Force overwriting of output files.")
    parser.add_argument('-l', '--lang', default='ja_JP.UTF-8')
    args = parser.parse_args()

    if args.recipe == 'help':
        extra_usage()
        sys.exit()
    (cd_info, track_list) = parse_info(args.recipe)

    if not check_headers(cd_info):
        sys.exit()
    if not check_wav_files(cd_info, track_list):
        sys.exit()
    do_encode(cd_info, track_list, args)
