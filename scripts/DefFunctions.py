#!/usr/bin/env python

# #/****************************************************************************
# #**
# #** Copyright (C) 2011 Andrey Kartashov .
##** All rights reserved.
##** Contact: Andrey Kartashov (porter@porter.st)
##**
##** This file is part of the global module of the genome-tools.
##**
##** GNU Lesser General Public License Usage
##** This file may be used under the terms of the GNU Lesser General Public
##** License version 2.1 as published by the Free Software Foundation and
##** appearing in the file LICENSE.LGPL included in the packaging of this
##** file. Please review the following information to ensure the GNU Lesser
##** General Public License version 2.1 requirements will be met:
##** http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
##**
##** Other Usage
##** Alternatively, this file may be used in accordance with the terms and
##** conditions contained in a signed written agreement between you and Andrey Kartashov.
##**
##****************************************************************************/

import os
import sys

import smtplib
import glob
import subprocess as s
import time
import re
import random
import MySQLdb
import warnings
import string


def send_mail(toaddrs, body):
    fromaddr = 'biowrdrobe@biowardrobe.com'
    # Add the From: and To: headers at the start!
    msg = ("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n"
           % (fromaddr, toaddrs, body))
    msg = msg + body

    server = smtplib.SMTP('localhost')
    server.set_debuglevel(1)
    server.sendmail(fromaddr, toaddrs, msg)
    server.quit()


def check_pid(pid):
    """ Check For the existence of a unix pid. """
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def check_running(fname):
    if os.path.isfile(fname):
        old_pid = file(fname, 'r').readline()
        if old_pid and check_pid(int(old_pid)):
            sys.exit()
    file(fname, 'w').write(str(os.getpid()))


def file_exist(basedir, fname, extension):
    return glob.glob(basedir + '/' + fname + '.' + extension)

def del_in_dir(path, exc=""):
    #TODO: ? do we need / protection?
    try:
        os.chdir(path)
        for root, dirs, files in os.walk("./", topdown=False):
            for name in files:
                if exc != "" and exc in name:
                    continue
                os.remove(os.path.join(root, name))
    except:
        pass


def macs_data(infile):
    FRAGMENT = 0
    ISLANDS = 0
    FNAME = infile
    for line in open(FNAME + '_macs_peaks.xls'):
        if re.match('^# d = ', line):
            FRAGMENT = int(line.split('d = ')[1])
            continue
        if re.match('^#', line):
            continue
        if line.strip() != "":
            ISLANDS = ISLANDS + 1
    ISLANDS = ISLANDS - 1  # header
    return [FRAGMENT, ISLANDS]


def upload_macsdata(conn, infile, dbexp, db):
    warnings.filterwarnings('ignore', category=MySQLdb.Warning)
    cursor = conn.cursor()

    table_name = dbexp + '.`' + infile + '_islands`'
    gb_table_name = db + '.`' + string.replace(infile, "-", "_") + '_islands`'

    cursor.execute("DROP TABLE IF EXISTS " + table_name)
    cursor.execute("DROP TABLE IF EXISTS " + gb_table_name)

    cursor.execute(""" CREATE TABLE """ + table_name + """
        ( chrom VARCHAR(255) NOT NULL,
    start INT(10) UNSIGNED NOT NULL,
    end INT(10) UNSIGNED NOT NULL,
    length INT(10) UNSIGNED NOT NULL,
    abssummit INT(10),
    pileup FLOAT,
    log10p FLOAT,
    foldenrich FLOAT,
    log10q FLOAT,
    INDEX chrom_idx (chrom) USING BTREE,
    INDEX start_idx (start) USING BTREE,
    INDEX end_idx (end) USING BTREE
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8 """)
    conn.commit()

    cursor.execute(""" CREATE TABLE """ + gb_table_name + """
        (
    bin int(7) unsigned NOT NULL,
    chrom varchar(255) NOT NULL,
    chromStart int(10) unsigned NOT NULL,
    chromEnd int(10) unsigned NOT NULL,
    name varchar(255) NOT NULL,
    score int(5) not null,
    INDEX bin_idx (bin) using btree,
    INDEX chrom_idx (chrom) using btree,
    INDEX chrom_start_idx (chromStart) using btree,
    INDEX chrom_end_idx (chromEnd) using btree
    ) ENGINE=MyISAM DEFAULT CHARSET=utf8 """)
    conn.commit()

    if len(file_exist('.', infile + '_macs_peaks', 'xls')) != 1:
        return ['Error', ' MACS peak file does not exist']


    SQL = "INSERT INTO " + table_name + " (chrom,start,end,length,abssummit,pileup,log10p,foldenrich,log10q) VALUES"
    SQLB = "INSERT INTO " + table_name + " (chrom,start,end,length,pileup,log10p,foldenrich,log10q) VALUES"

    skip = True
    broad = False
    islands = 0
    for line in open(infile + '_macs_peaks.xls', 'r'):
        if re.match('^#', line) or line.strip() == "":
            continue
        if skip:
            a = line.strip().split('\t')
            if not broad:
                broad = ("pileup" in a[4])
            skip = False
            continue
        a = line.strip().split('\t')
        islands += 1
        try:
            if broad:
                cursor.execute(SQLB + " (%s,%s,%s,%s,%s,%s,%s,%s)", (a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]))
            else:
                cursor.execute(SQL + " (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                               (a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]))
            conn.commit()
        except Exception, e:
            return ['Error', line + ":" + str(e)]
    cursor.execute("""insert into  """ + gb_table_name +
                   """ (bin, chrom, chromStart, chromEnd, name, score)
                    select 0 as bin, chrom, start as chromStart, end as chromEnd,
                    max(log10p) as name, max(log10q) as score
                    from """ + table_name + """ group by chrom,start,end; """)
    conn.commit()

    return ['Success', islands]


def run_macs(infile, gsize="2.35e9", fragsize=150, fragforce=False, pair=False, broad=False, force=None, control=""):

    shiftsize = int(fragsize / 2)

    if len(file_exist('.', infile, 'bam')) != 1:
        return ['Error', 'Bam file does not exist']

    if force:
        FL = file_exist('.', infile + '_macs_peaks', 'xls')
        if len(FL) == 1:
            os.unlink(FL[0])

    if len(file_exist('.', infile + '_macs_peaks', 'xls')) == 1:
        return ['Success', ' Macs analyzes done ']

    # samtools view -H b4f4ede6-e866-11e3-9546-ac162d784858.bam |grep 'SQ'| awk -F'LN:' '{print $2}'|paste -sd+ | bc
    # at least macs 2.1
    cmd = 'macs2 callpeak -t ' + infile + '.bam'
    if control != "":
        cmd += " -c "+control
    else:
        cmd += " --nolambda "
    cmd += ' -n ' + infile + '_macs -g ' + gsize + ' -m 4 40  --verbose 3 '

    if pair:
        cmd += ' -f BAMPE '
    else:
        cmd += ' -f BAM '

    if fragforce:
        cmd += ' --nomodel --extsize ' + str(fragsize) # + ' --shift ' + str(shiftsize)
    else:
        cmd += " --bw " + str(fragsize)

    if broad:
        cmd += " --broad "
    else:
        cmd += " --call-summits "

    cmd += ' --keep-dup auto -q 0.05  >./' + infile + '_macs.log 2>&1'

    try:
        s.check_output(cmd, shell=True)
        return ['Success', ' MACS finished ']
    except Exception, e:
        return ['Error', str(e)]


def run_bedgraph(infile, db, fragment, isRNA, pair, force=None):
    FL = file_exist('.', infile, 'log')

    if force and len(FL) == 1:
        os.unlink(FL[0])

    if len(file_exist('.', infile, 'log')) == 1:
        return ['Success', ' Bedgraph uploaded']

    cmd = 'bam2bedgraph -sql_table="\`' + db + '\`.\`' + string.replace(infile, "-", "_") \
          + '_wtrack\`" -in="' + infile + '.bam" -out="'
    cmd += infile + '.out" -log="' + infile + '.log"' + ' -no-bed-file '

    if isRNA == 1:
        cmd += ' -bed_type=2 -rna_seq="RNA" -bed_format=4 '
    elif isRNA == 2:
        cmd += ' -bed_type=2 -rna_seq="dUTP" -bed_format=8 '
    else:
        cmd += ' -bed_format=4 '
        if pair:
            cmd += ' -bed_type=2 '
        else:
            cmd += ' -bed_window=' + str(fragment) + ' -bed_siteshift=' + str(fragment / 2)
            cmd += ' -bed_type=3 '

    cmd += ' -bed_normalize '
    try:
        s.check_output(cmd, shell=True)
        return ['Success', ' Upload to genome browser success']
    except Exception, e:
        return ['Error', str(e)]


def run_fence_old(infile, pair, trimmed):
    if len(file_exist('.', infile, 'fence')) == 1:
        return ['Success', 'Fence file exists']
    if trimmed:
        if pair:
            cmd = 'fence.py --in="' + infile + '_trimmed;' + infile + '_trimmed_2" >' + infile + '.fence'
        else:
            cmd = 'fence.py --in="' + infile + '_trimmed.fastq" >' + infile + '.fence'
    else:
        if pair:
            cmd = 'fence.py --in="' + infile + ';' + infile + '_2" >' + infile + '.fence'
        else:
            cmd = 'fence.py --in="' + infile + '.fastq" >' + infile + '.fence'
    try:
        s.Popen(cmd, shell=True)
        return ['Success', ' Fence backgrounded']
    except Exception, e:
        return ['Error', str(e)]


def run_fence(infile, pair, bzip=False, force=False):
    ext = 'fastxstat'
    fl = file_exist('.', infile, ext)

    if force and len(fl) == 1:
        os.unlink(fl[0])

    if len(fl) == 1 and not force:
        return ['Success', 'Fastx stat file exists']

    cmd = ''

    def outp(inf):
        return ' -o "' + inf + '.' + ext + '"'

    def bzipped(inf):
        return 'bzcat "' + inf + '.fastq.bz2"| fastx_quality_stats ' + outp(inf)

    def common(inf):
        return 'fastx_quality_stats -i "' + inf + '.fastq" ' + outp(inf)

    if pair:
        if bzip:
            cmd = bzipped(infile) + ';' + bzipped(infile + '_2')
        else:
            cmd = common(infile) + ';' + common(infile + '_2')
    else:
        if bzip:
            cmd = bzipped(infile)
        else:
            cmd = common(infile)
    try:
        s.Popen(cmd, shell=True)
        return ['Success', ' Fastx backgrounded']
    except Exception, e:
        return ['Error', str(e)]


def run_atp(lid):
    cmd = 'atdp -avd_luid="' + lid + '" -log="./AverageTagDensity.log" '
    cmd += ' -sam_twicechr="chrX chrY" -sam_ignorechr="chrM" -avd_window=5000 -avd_smooth=50 -avd_heat_window=200 '

    try:
        s.check_output(cmd, shell=True)
        return ['Success', ' ATP finished ']
    except Exception, e:
        return ['Error', str(e)]


def do_trimm(uid, pair, _left, _right):
    left = str(_left)
    right = str(_right)
    if pair:
        cmd = 'cat ' + uid + '.fastq | trimmer.py -l' + left + ' -r' + right + '>' + uid + '_trimmed.fastq;'
        cmd += 'cat ' + uid + '_2.fastq | trimmer.py -l' + left + ' -r' + right + '>' + uid + '_trimmed_2.fastq'
    else:
        cmd = 'cat ' + uid + '.fastq | trimmer.py -l' + left + ' -r' + right + '>' + uid + '_trimmed.fastq;'
    try:
        s.check_output(cmd, shell=True)
        return ['Success', ' Trim is done ']
    except Exception, e:
        return ['Error', str(e)]
