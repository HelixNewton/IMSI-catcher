#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Author: Oros
# Contributors :
#  purwowd
#  puyoulu
#  1kali2kali
#  petterreinholdtsen
#  nicoeg
#  dspinellis
#  fdl <Frederic.Lehobey@proxience.com>
#  lapolis
# 2024-12-19
# License : CC0 1.0 Universal

"""
This program shows you IMSI numbers of cellphones around you.


/! This program was made to understand how GSM network work. Not for bad hacking !
"""

import ctypes
import csv
import json
from optparse import OptionParser
import datetime
import io
import sys
import socket

imsitracker = None


class tracker:
    # in minutes
    purgeTimer = 10  # default 10 min

    show_all_tmsi = False
    mcc_codes = None
    sqlite_con = None
    mysql_con = None
    mysql_cur = None
    textfilePath = None
    output_function = None
    output_format = "table"
    show_meta = False
    csv_writer = None
    csv_file = None
    cell_arfcn = None
    cell_last_seen = None

    def __init__(self):
        self.imsistate = {}
        self.imsis = []
        self.tmsis = {}
        self.nb_IMSI = 0
        self.mcc = ""
        self.mnc = ""
        self.lac = ""
        self.cell = ""
        self.country = ""
        self.brand = ""
        self.operator = ""
        self.show_all_tmsi = False
        self.sqlite_con = None
        self.mysql_con = None
        self.mysql_cur = None
        self.textfilePath = None
        self.output_format = "table"
        self.show_meta = False
        self.csv_writer = None
        self.csv_file = None
        self.cell_arfcn = None
        self.cell_last_seen = None
        self.load_mcc_codes()
        self.track_this_imsi("")
        self.output_function = self.output

    def set_output_function(self, new_output_function):
        # New output function need this field :
        # cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, timestamp, packet=None
        self.output_function = new_output_function

    def set_output_format(self, output_format, show_meta=False):
        self.output_format = output_format
        self.show_meta = show_meta
        if output_format == "json":
            self.output_function = self.output_json
        elif output_format == "csv":
            self.output_function = self.output_csv
        else:
            self.output_function = self.output

    def track_this_imsi(self, imsi_to_track):
        self.imsi_to_track = imsi_to_track
        self.imsi_to_track_len = len(imsi_to_track)

    # return something like '0xd9605460'
    def str_tmsi(self, tmsi):
        if tmsi != "":
            new_tmsi = "0x"
            for a in tmsi:
                c = hex(a)
                if len(c) == 4:
                    new_tmsi += str(c[2]) + str(c[3])
                else:
                    new_tmsi += "0" + str(c[2])
            return new_tmsi
        else:
            return ""

    def decode_imsi(self, imsi):
        new_imsi = ''
        for a in imsi:
            c = hex(a)
            if len(c) == 4:
                new_imsi += str(c[3]) + str(c[2])
            else:
                new_imsi += str(c[2]) + "0"

        mcc = new_imsi[1:4]
        mnc = new_imsi[4:6]
        return new_imsi, mcc, mnc

    # return something like
    # '208 20 1752XXXXXX', 'France', 'Bouygues', 'Bouygues Telecom'
    def str_imsi(self, imsi, packet=""):
        new_imsi, mcc, mnc = self.decode_imsi(imsi)
        country = ""
        brand = ""
        operator = ""

        if mcc in self.mcc_codes:
            if mnc in self.mcc_codes[mcc]:
                brand, operator, country, _ = self.mcc_codes[mcc][mnc]
                new_imsi = f"{mcc} {mnc} {new_imsi[6:]}"
            elif mnc + new_imsi[6:7] in self.mcc_codes[mcc]:
                mnc += new_imsi[6:7]
                brand, operator, country, _ = self.mcc_codes[mcc][mnc]
                new_imsi = f"{mcc} {mnc} {new_imsi[7:]}"

        else:
            country = f"Unknown MCC {mcc}"
            brand = f"Unknown MNC {mnc}"
            operator = f"Unknown MNC {mnc}"
            new_imsi = f"{mcc} {mnc} {new_imsi[6:]}"

        try:
            return new_imsi, country, brand, operator
        except Exception:
            # m = ""
            print("Error", packet, new_imsi, country, brand, operator)
        return "", "", "", ""

    def load_mcc_codes(self):
        # mcc codes form https://en.wikipedia.org/wiki/Mobile_Network_Code
        with io.open('mcc-mnc/mcc_codes.json', 'r', encoding='utf8') as file:
            self.mcc_codes = json.load(file)

    def current_cell(self, mcc, mnc, lac, cell, arfcn=None):
        brand = ""
        operator = ""
        country = ""
        if mcc in self.mcc_codes and mnc in self.mcc_codes[mcc]:
            brand, operator, country, _ = self.mcc_codes[mcc][mnc]
        else:
            country = f"Unknown MCC {mcc}"
            brand = f"Unknown MNC {mnc}"
            operator = f"Unknown MNC {mnc}"
        self.mcc = str(mcc)
        self.mnc = str(mnc)
        self.lac = str(lac)
        self.cell = str(cell)
        self.country = country
        self.brand = brand
        self.operator = operator
        self.cell_arfcn = str(arfcn) if arfcn is not None else None
        self.cell_last_seen = datetime.datetime.utcnow().replace(microsecond=0)

    def cell_context_for_event(self, arfcn):
        empty_context = {
            "mcc": "",
            "mnc": "",
            "lac": "",
            "cell": "",
            "country": "",
            "brand": "",
            "operator": "",
            "cell_status": "unknown",
        }

        if self.cell_arfcn is None or self.cell_last_seen is None:
            return empty_context

        if arfcn is None or str(arfcn) != self.cell_arfcn:
            context = empty_context.copy()
            context["cell_status"] = "stale"
            return context

        context = {
            "mcc": str(self.mcc),
            "mnc": str(self.mnc),
            "lac": str(self.lac),
            "cell": str(self.cell),
            "country": self.country,
            "brand": self.brand,
            "operator": self.operator,
            "cell_status": "current",
        }
        return context

    def sqlite_file(self, filename):
        import sqlite3  # Avoid pulling in sqlite3 when not saving
        print("Saving to SQLite database in %s" % filename)
        self.sqlite_con = sqlite3.connect(filename)
        self.sqlite_con.text_factory = str
        self.sqlite_con.execute(
            "CREATE TABLE IF NOT EXISTS observations("
            "stamp datetime, "
            "tmsi1 text, "
            "tmsi2 text, "
            "imsi text, "
            "imsicountry text, "
            "imsibrand text, "
            "imsioperator text, "
            "mcc integer, "
            "mnc integer, "
            "lac integer, "
            "cell integer, "
            "arfcn integer, "
            "timeslot integer, "
            "sub_slot integer, "
            "signal_dbm integer, "
            "snr_db integer, "
            "frame_number integer, "
            "channel_type integer, "
            "message_type text, "
            "cell_status text"
            ");"
        )

    def text_file(self, filename):
        txt = open(filename, "w", newline="")
        self.csv_file = txt
        self.csv_writer = csv.writer(txt)
        self.csv_writer.writerow([
            "stamp",
            "tmsi1",
            "tmsi2",
            "imsi",
            "imsicountry",
            "imsibrand",
            "imsioperator",
            "mcc",
            "mnc",
            "lac",
            "cell",
            "arfcn",
            "timeslot",
            "sub_slot",
            "signal_dbm",
            "snr_db",
            "frame_number",
            "channel_type",
            "message_type",
            "cell_status",
        ])
        self.textfilePath = filename

    def mysql_file(self):
        import os.path
        if os.path.isfile('.env'):
            import MySQLdb as mdb
            from decouple import config
            self.mysql_con = mdb.connect(config("MYSQL_HOST"), config("MYSQL_USER"), config("MYSQL_PASSWORD"), config("MYSQL_DB"))
            self.mysql_cur = self.mysql_con.cursor()
            # Check MySQL connection
            if self.mysql_cur:
                print("mysql connection is success :)")
            else:
                print("mysql connection is failed!")
                exit()
        else:
            print("create file .env first")
            exit()

    def close(self):
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        if self.sqlite_con:
            self.sqlite_con.close()
            self.sqlite_con = None
        if self.mysql_cur:
            self.mysql_cur.close()
            self.mysql_cur = None
        if self.mysql_con:
            self.mysql_con.close()
            self.mysql_con = None

    def build_record(self, cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, meta=None):
        meta = meta or {}
        record = {
            "count": str(cpt),
            "tmsi1": tmsi1,
            "tmsi2": tmsi2,
            "imsi": imsi,
            "imsicountry": imsicountry,
            "imsibrand": imsibrand,
            "imsioperator": imsioperator,
            "mcc": str(mcc),
            "mnc": str(mnc),
            "lac": str(lac),
            "cell": str(cell),
            "timestamp": now.isoformat(),
            "arfcn": str(meta.get("arfcn", "")),
            "timeslot": str(meta.get("timeslot", "")),
            "sub_slot": str(meta.get("sub_slot", "")),
            "signal_dbm": str(meta.get("signal_dbm", "")),
            "snr_db": str(meta.get("snr_db", "")),
            "frame_number": str(meta.get("frame_number", "")),
            "channel_type": str(meta.get("channel_type", "")),
            "message_type": str(meta.get("message_type", "")),
            "cell_status": str(meta.get("cell_status", "")),
        }
        return record

    def output(self, cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, packet=None, meta=None):
        record = self.build_record(cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, meta=meta)
        fields = [
            f"{record['count']:7s}",
            f"{record['tmsi1']:10s}",
            f"{record['tmsi2']:10s}",
            f"{record['imsi']:17s}",
            f"{record['imsicountry']:16s}",
            f"{record['imsibrand']:14s}",
            f"{record['imsioperator']:21s}",
            f"{record['mcc']:4s}",
            f"{record['mnc']:5s}",
            f"{record['lac']:6s}",
            f"{record['cell']:6s}",
        ]
        if self.show_meta:
            fields.extend([
                f"{record['arfcn']:5s}",
                f"{record['timeslot']:2s}",
                f"{record['sub_slot']:3s}",
                f"{record['signal_dbm']:6s}",
                f"{record['snr_db']:5s}",
                f"{record['frame_number']:10s}",
                f"{record['message_type']:14s}",
                f"{record['cell_status']:10s}",
            ])
        fields.append(record["timestamp"])
        print(" ; ".join(fields))

    def output_json(self, cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, packet=None, meta=None):
        record = self.build_record(cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, meta=meta)
        print(json.dumps(record, ensure_ascii=False))

    def output_csv(self, cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, packet=None, meta=None):
        record = self.build_record(cpt, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, now, meta=meta)
        writer = csv.writer(sys.stdout)
        columns = [
            record["count"],
            record["tmsi1"],
            record["tmsi2"],
            record["imsi"],
            record["imsicountry"],
            record["imsibrand"],
            record["imsioperator"],
            record["mcc"],
            record["mnc"],
            record["lac"],
            record["cell"],
            record["arfcn"],
            record["timeslot"],
            record["sub_slot"],
            record["signal_dbm"],
            record["snr_db"],
            record["frame_number"],
            record["channel_type"],
            record["message_type"],
            record["cell_status"],
            record["timestamp"],
        ]
        writer.writerow(columns)

    def pfields(self, cpt, tmsi1, tmsi2, imsi, arfcn, packet=None, meta=None):
        imsicountry = ""
        imsibrand = ""
        imsioperator = ""
        context = self.cell_context_for_event(arfcn)
        if imsi:
            imsi, imsicountry, imsibrand, imsioperator = self.str_imsi(imsi, packet)
        elif context["country"] or context["brand"] or context["operator"]:
            imsicountry = context["country"]
            imsibrand = context["brand"]
            imsioperator = context["operator"]
        else:
            imsi = ""
        now = datetime.datetime.now()
        meta = dict(meta or {})
        meta["cell_status"] = context["cell_status"]
        self.output_function(
            cpt,
            tmsi1,
            tmsi2,
            imsi,
            imsicountry,
            imsibrand,
            imsioperator,
            context["mcc"],
            context["mnc"],
            context["lac"],
            context["cell"],
            now,
            packet,
            meta,
        )

        if self.textfilePath:
            self.csv_writer.writerow([
                str(now),
                tmsi1,
                tmsi2,
                imsi,
                imsicountry,
                imsibrand,
                imsioperator,
                context["mcc"],
                context["mnc"],
                context["lac"],
                context["cell"],
                meta.get("arfcn", ""),
                meta.get("timeslot", ""),
                meta.get("sub_slot", ""),
                meta.get("signal_dbm", ""),
                meta.get("snr_db", ""),
                meta.get("frame_number", ""),
                meta.get("channel_type", ""),
                meta.get("message_type", ""),
                meta.get("cell_status", ""),
            ])
            self.csv_file.flush()

        if tmsi1 == "":
            tmsi1 = None
        if tmsi2 == "":
            tmsi2 = None

        if self.sqlite_con:
            self.sqlite_con.execute(
               u"INSERT INTO observations (stamp, tmsi1, tmsi2, imsi, imsicountry, imsibrand, imsioperator, mcc, mnc, lac, cell, arfcn, timeslot, sub_slot, signal_dbm, snr_db, frame_number, channel_type, message_type, cell_status) "
               + "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
               (
                   now,
                   tmsi1,
                   tmsi2,
                   imsi,
                   imsicountry,
                   imsibrand,
                   imsioperator,
                   context["mcc"],
                   context["mnc"],
                   context["lac"],
                   context["cell"],
                   meta.get("arfcn"),
                   meta.get("timeslot"),
                   meta.get("sub_slot"),
                   meta.get("signal_dbm"),
                   meta.get("snr_db"),
                   meta.get("frame_number"),
                   meta.get("channel_type"),
                   meta.get("message_type"),
                   meta.get("cell_status"),
               )
            )
            self.sqlite_con.commit()
            pass

        if self.mysql_cur:
            print("saving data to db...")
            # Example query
            query = (
                "INSERT INTO `imsi` "
                "(`tmsi1`, `tmsi2`, `imsi`, `mcc`, `mnc`, `lac`, `cell_id`, `stamp`, `deviceid`, `arfcn`, `timeslot`, `sub_slot`, `signal_dbm`, `snr_db`, `frame_number`, `channel_type`, `message_type`, `cell_status`) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            )
            arg = (
                tmsi1,
                tmsi2,
                imsi,
                context["mcc"],
                context["mnc"],
                context["lac"],
                context["cell"],
                now,
                "rtl",
                meta.get("arfcn"),
                meta.get("timeslot"),
                meta.get("sub_slot"),
                meta.get("signal_dbm"),
                meta.get("snr_db"),
                meta.get("frame_number"),
                meta.get("channel_type"),
                meta.get("message_type"),
                meta.get("cell_status"),
            )
            self.mysql_cur.execute(query, arg)
            self.mysql_con.commit()

    def header(self):
        if self.output_format == "json":
            return
        if self.output_format == "csv":
            csv.writer(sys.stdout).writerow([
                "Nb IMSI",
                "TMSI-1",
                "TMSI-2",
                "IMSI",
                "country",
                "brand",
                "operator",
                "MCC",
                "MNC",
                "LAC",
                "CellId",
                "ARFCN",
                "TS",
                "SS",
                "dBm",
                "SNR",
                "Frame",
                "ChannelType",
                "MsgType",
                "CellState",
                "Timestamp",
            ])
            return
        columns = [
            f"{'Nb IMSI':7s}",
            f"{'TMSI-1':10s}",
            f"{'TMSI-2':10s}",
            f"{'IMSI':17s}",
            f"{'country':16s}",
            f"{'brand':14s}",
            f"{'operator':21s}",
            f"{'MCC':4s}",
            f"{'MNC':5s}",
            f"{'LAC':6s}",
            f"{'CellId':6s}",
        ]
        if self.show_meta:
            columns.extend([
                f"{'ARFCN':5s}",
                f"{'TS':2s}",
                f"{'SS':3s}",
                f"{'dBm':6s}",
                f"{'SNR':5s}",
                f"{'Frame':10s}",
                f"{'MsgType':14s}",
                f"{'CellState':10s}",
            ])
        columns.append("Timestamp")
        print(" ; ".join(columns))

    def register_imsi(self, arfcn, imsi1="", imsi2="", tmsi1="", tmsi2="", p="", meta=None):
        do_print = False
        n = ''
        tmsi1 = self.str_tmsi(tmsi1)
        tmsi2 = self.str_tmsi(tmsi2)
        if imsi1:
            self.imsi_seen(imsi1, arfcn)
        if imsi2:
            self.imsi_seen(imsi2, arfcn)
        if imsi1 and (not self.imsi_to_track or imsi1[:self.imsi_to_track_len] == self.imsi_to_track):
            if imsi1 not in self.imsis:
                # new IMSI
                do_print = True
                self.imsis.append(imsi1)
                self.nb_IMSI += 1
                n = self.nb_IMSI
            if self.tmsis and tmsi1 and (tmsi1 not in self.tmsis or self.tmsis[tmsi1] != imsi1):
                # new TMSI to an ISMI
                do_print = True
                self.tmsis[tmsi1] = imsi1
            if self.tmsis and tmsi2 and (tmsi2 not in self.tmsis or self.tmsis[tmsi2] != imsi1):
                # new TMSI to an ISMI
                do_print = True
                self.tmsis[tmsi2] = imsi1

        if imsi2 and (not self.imsi_to_track or imsi2[:self.imsi_to_track_len] == self.imsi_to_track):
            if imsi2 not in self.imsis:
                # new IMSI
                do_print = True
                self.imsis.append(imsi2)
                self.nb_IMSI += 1
                n = self.nb_IMSI
            if self.tmsis and tmsi1 and (tmsi1 not in self.tmsis or self.tmsis[tmsi1] != imsi2):
                # new TMSI to an ISMI
                do_print = True
                self.tmsis[tmsi1] = imsi2
            if self.tmsis and tmsi2 and (tmsi2 not in self.tmsis or self.tmsis[tmsi2] != imsi2):
                # new TMSI to an ISMI
                do_print = True
                self.tmsis[tmsi2] = imsi2

                # Unreachable or rarely reached branch? Add unit-test.
        if not imsi1 and not imsi2 and tmsi1 and tmsi2:
            if self.tmsis and tmsi2 in self.tmsis:
                # switch the TMSI
                do_print = True
                imsi1 = self.tmsis[tmsi2]
                self.tmsis[tmsi1] = imsi1
                del self.tmsis[tmsi2]

        if do_print:
            if imsi1:
                self.pfields(str(n), tmsi1, tmsi2, imsi1, arfcn, p, meta=meta)
            if imsi2:
                self.pfields(str(n), tmsi1, tmsi2, imsi2, arfcn, p, meta=meta)

        if not imsi1 and not imsi2:
            # Register IMSI as seen if a TMSI believed to
            # belong to the IMSI is seen.
            if self.tmsis and tmsi1 and tmsi1 in self.tmsis and "" != self.tmsis[tmsi1]:
                self.imsi_seen(self.tmsis[tmsi1], arfcn)
            if self.show_all_tmsi:
                do_print = False
                if tmsi1 and tmsi1 not in self.tmsis:
                    do_print = True
                    self.tmsis[tmsi1] = ""
                if tmsi2 and tmsi2 not in self.tmsis:
                    do_print = True
                    self.tmsis[tmsi2] = ""
                if do_print:
                    self.pfields(str(n), tmsi1, tmsi2, None, arfcn, p, meta=meta)

    def imsi_seen(self, imsi, arfcn):
        now = datetime.datetime.utcnow().replace(microsecond=0)
        imsi, mcc, mnc = self.decode_imsi(imsi)
        if imsi in self.imsistate:
            self.imsistate[imsi]["lastseen"] = now
        else:
            self.imsistate[imsi] = {
                "firstseen": now,
                "lastseen": now,
                "imsi": imsi,
                "arfcn": arfcn,
            }
        self.imsi_purge_old()

    def imsi_purge_old(self):
        now = datetime.datetime.utcnow().replace(microsecond=0)
        maxage = datetime.timedelta(minutes=self.purgeTimer)
        limit = now - maxage
        remove = [imsi for imsi in self.imsistate if limit > self.imsistate[imsi]["lastseen"]]
        for k in remove:
            del self.imsistate[k]
        # keys = self.imsistate.keys()
        # for imsi in keys:
        #   if limit > self.imsistate[imsi]["lastseen"]:
        #       del self.imsistate[imsi]
        #       keys = self.imsistate.keys()


class gsmtap_hdr(ctypes.BigEndianStructure):
    _pack_ = 1
    # Based on gsmtap_hdr structure in <grgsm/gsmtap.h> from gr-gsm
    _fields_ = [
        ("version", ctypes.c_ubyte),
        ("hdr_len", ctypes.c_ubyte),
        ("type", ctypes.c_ubyte),
        ("timeslot", ctypes.c_ubyte),
        ("arfcn", ctypes.c_uint16),
        ("signal_dbm", ctypes.c_ubyte),
        ("snr_db", ctypes.c_ubyte),
        ("frame_number", ctypes.c_uint32),
        ("sub_type", ctypes.c_ubyte),
        ("antenna_nr", ctypes.c_ubyte),
        ("sub_slot", ctypes.c_ubyte),
        ("res", ctypes.c_ubyte),
    ]

    def __repr__(self):
        return "%s(version=%d, hdr_len=%d, type=%d, timeslot=%d, arfcn=%d, signal_dbm=%d, snr_db=%d, frame_number=%d, sub_type=%d, antenna_nr=%d, sub_slot=%d, res=%d)" % (
            self.__class__, self.version, self.hdr_len, self.type,
            self.timeslot, self.arfcn, self.signal_dbm, self.snr_db,
            self.frame_number, self.sub_type, self.antenna_nr, self.sub_slot,
            self.res,
        )


# return mcc mnc, lac, cell, country, brand, operator
def find_cell(gsm, udpdata, t=None):
    # find_cell() update all following variables
    global mcc
    global mnc
    global lac
    global cell
    global country
    global brand
    global operator

    """
    Dump of a packet from wireshark

    /! there are an offset of 0x2a
    0x12 (from the code) + 0x2a (offset) == 0x3c (in documentation's dump)

            0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
    0010   00 43 9a 6b 40 00 40 11 a2 3c 7f 00 00 01 7f 00
    0020   00 01 ed d1 12 79 00 2f fe 42 02 04 01 00 00 00
    0030   cc 00 00 07 9b 2c 01 00 00 00 49 06 1b 61 9d 02
    0040   f8 02 01 9c c8 03 1e 53 a5 07 79 00 00 80 01 40
    0050   db

    Channel Type: BCCH (1)
                            6
    0030                     01

    0x36 - 0x2a = position p[0x0c]


    Message Type: System Information Type 3
                                                c
    0030                                       1b

    0x3c - 0x2a = position p[0x12]

    Cell CI: 0x619d (24989)
                                                d  e
    0030                                          61 9d

    0x3d - 0x2a = position p[0x13]
    0x3e - 0x2a = position p[0x14]

    Location Area Identification (LAI) - 208/20/412
    Mobile Country Code (MCC): France (208) 0x02f8
    Mobile Network Code (MNC): Bouygues Telecom (20) 0xf802
    Location Area Code (LAC): 0x019c (412)
            0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
    0030                                                02
    0040   f8 02 01 9c
    """
    if gsm.sub_type == 0x01:  # Channel Type == BCCH (0)
        p = bytearray(udpdata)
        if p[0x12] == 0x1b:  # (0x12 + 0x2a = 0x3c) Message Type: System Information Type 3
            mcc, mnc = decode_plmn(p[0x15], p[0x16], p[0x17])
            lac = p[0x18] * 256 + p[0x19]
            cell = p[0x13] * 256 + p[0x14]
            t.current_cell(mcc, mnc, lac, cell, arfcn=gsm.arfcn)


def decode_plmn(octet1, octet2, octet3):
    mcc = f"{octet1 & 0x0f}{(octet1 >> 4) & 0x0f}{octet2 & 0x0f}"
    mnc_digit3 = (octet2 >> 4) & 0x0f
    mnc = f"{octet3 & 0x0f}{(octet3 >> 4) & 0x0f}"
    if mnc_digit3 != 0x0f:
        mnc += str(mnc_digit3)
    return mcc, mnc


def message_type_name(message_type):
    mapping = {
        0x1B: "SI3",
        0x21: "PagingReq1",
        0x22: "PagingReq2",
        0x3F: "ImmAssign",
    }
    return mapping.get(message_type, f"0x{message_type:02x}")


def packet_meta(gsm, message_type):
    signal_dbm = gsm.signal_dbm
    if signal_dbm > 127:
        signal_dbm -= 256
    return {
        "arfcn": gsm.arfcn,
        "timeslot": gsm.timeslot,
        "sub_slot": gsm.sub_slot,
        "signal_dbm": signal_dbm,
        "snr_db": gsm.snr_db,
        "frame_number": gsm.frame_number,
        "channel_type": gsm.sub_type,
        "message_type": message_type_name(message_type),
    }


def find_imsi(udpdata, t=None):
    if t is None:
        t = imsitracker

    # Create object representing gsmtap header in UDP payload
    gsm = gsmtap_hdr.from_buffer_copy(udpdata)

    if gsm.sub_type == 0x1:  # Channel Type == BCCH (0)
        # Update global cell info if found in package
        # FIXME : when you change the frequency, this informations is
        # not immediately updated.  So you could have wrong values when
        # printing IMSI :-/
        find_cell(gsm, udpdata, t=t)
    else:  # Channel Type != BCCH (0)
        p = bytearray(udpdata)
        meta = packet_meta(gsm, p[0x12])
        tmsi1 = ""
        tmsi2 = ""
        imsi1 = ""
        imsi2 = ""
        if p[0x12] == 0x21:  # Message Type: Paging Request Type 1
            if p[0x14] == 0x08 and (p[0x15] & 0x1) == 0x1:  # Channel 1: TCH/F (Full rate) (2)
                # Mobile Identity 1 Type: IMSI (1)
                """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 1c d4 40 00 40 11 1f d4 7f 00 00 01 7f 00
                0020   00 01 c2 e4 12 79 00 2f fe 42 02 04 01 00 00 00
                0030   c9 00 00 16 21 26 02 00 07 00 31 06 21 00 08 XX
                0040   XX XX XX XX XX XX XX 2b 2b 2b 2b 2b 2b 2b 2b 2b
                0050   2b
                XX XX XX XX XX XX XX XX = IMSI
                """
                imsi1 = p[0x15:][:8]
                # p[0x10] == 0x59 = l2 pseudo length value: 22
                if p[0x10] == 0x59 and p[0x1E] == 0x08 and (p[0x1F] & 0x1) == 0x1:  # Channel 2: TCH/F (Full rate) (2)
                    # Mobile Identity 2 Type: IMSI (1)
                    """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 90 95 40 00 40 11 ac 12 7f 00 00 01 7f 00
                0020   00 01 b4 1c 12 79 00 2f fe 42 02 04 01 00 00 00
                0030   c8 00 00 16 51 c6 02 00 08 00 59 06 21 00 08 YY
                0040   YY YY YY YY YY YY YY 17 08 XX XX XX XX XX XX XX
                0050   XX
                YY YY YY YY YY YY YY YY = IMSI 1
                XX XX XX XX XX XX XX XX = IMSI 2
                    """
                    imsi2 = p[0x1F:][:8]
                elif p[0x10] == 0x4d and p[0x1E] == 0x05 and p[0x1F] == 0xf4:  # Channel 2: TCH/F (Full rate) (2)
                    # Mobile Identity - Mobile Identity 2 - IMSI
                    """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 f6 92 40 00 40 11 46 15 7f 00 00 01 7f 00
                0020   00 01 ab c1 12 79 00 2f fe 42 02 04 01 00 00 00
                0030   d8 00 00 23 3e be 02 00 05 00 4d 06 21 a0 08 YY
                0040   YY YY YY YY YY YY YY 17 05 f4 XX XX XX XX 2b 2b
                0050   2b
                YY YY YY YY YY YY YY YY = IMSI 1
                XX XX XX XX = TMSI
                    """
                    tmsi1 = p[0x20:][:4]

                t.register_imsi(gsm.arfcn, imsi1, imsi2, tmsi1, tmsi2, p, meta=meta)

            elif p[0x1B] == 0x08 and (p[0x1C] & 0x1) == 0x1:  # Channel 2: TCH/F (Full rate) (2)
                # Mobile Identity 2 Type: IMSI (1)
                """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 57 8e 40 00 40 11 e5 19 7f 00 00 01 7f 00
                0020   00 01 99 d4 12 79 00 2f fe 42 02 04 01 00 00 00
                0030   c7 00 00 11 05 99 02 00 03 00 4d 06 21 00 05 f4
                0040   yy yy yy yy 17 08 XX XX XX XX XX XX XX XX 2b 2b
                0050   2b
                yy yy yy yy = TMSI/P-TMSI - Mobile Identity 1
                XX XX XX XX XX XX XX XX = IMSI
                """
                tmsi1 = p[0x16:][:4]
                imsi2 = p[0x1C:][:8]
                t.register_imsi(gsm.arfcn, imsi1, imsi2, tmsi1, tmsi2, p, meta=meta)

            elif p[0x14] == 0x05 and (p[0x15] & 0x07) == 4:  # Mobile Identity - Mobile Identity 1 - TMSI/P-TMSI
                """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 b3 f7 40 00 40 11 88 b0 7f 00 00 01 7f 00
                0020   00 01 ce 50 12 79 00 2f fe 42 02 04 01 00 03 fd
                0030   d1 00 00 1b 03 5e 05 00 00 00 41 06 21 00 05 f4
                0040   XX XX XX XX 17 05 f4 YY YY YY YY 2b 2b 2b 2b 2b
                0050   2b
                XX XX XX XX = TMSI/P-TMSI - Mobile Identity 1
                YY YY YY YY = TMSI/P-TMSI - Mobile Identity 2
                """
                tmsi1 = p[0x16:][:4]
                if p[0x1B] == 0x05 and (p[0x1C] & 0x07) == 4:  # Mobile Identity - Mobile Identity 2 - TMSI/P-TMSI
                    tmsi2 = p[0x1D:][:4]
                else:
                    tmsi2 = ""

                t.register_imsi(gsm.arfcn, imsi1, imsi2, tmsi1, tmsi2, p, meta=meta)

        elif p[0x12] == 0x22:  # Message Type: Paging Request Type 2
            if p[0x1D] == 0x08 and (p[0x1E] & 0x1) == 0x1:  # Mobile Identity 3 Type: IMSI (1)
                """
                        0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
                0000   00 00 00 00 00 00 00 00 00 00 00 00 08 00 45 00
                0010   00 43 1c a6 40 00 40 11 20 02 7f 00 00 01 7f 00
                0020   00 01 c2 e4 12 79 00 2f fe 42 02 04 01 00 00 00
                0030   c9 00 00 16 20 e3 02 00 04 00 55 06 22 00 yy yy
                0040   yy yy zz zz zz 4e 17 08 XX XX XX XX XX XX XX XX
                0050   8b
                yy yy yy yy = TMSI/P-TMSI - Mobile Identity 1
                zz zz zz zz = TMSI/P-TMSI - Mobile Identity 2
                XX XX XX XX XX XX XX XX = IMSI
                """
                tmsi1 = p[0x14:][:4]
                tmsi2 = p[0x18:][:4]
                imsi2 = p[0x1E:][:8]
                t.register_imsi(gsm.arfcn, imsi1, imsi2, tmsi1, tmsi2, p, meta=meta)


def udpserver(port, prn):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_address = ('localhost', port)
    sock.bind(server_address)
    while True:
        udpdata, address = sock.recvfrom(4096)
        if prn:
            prn(udpdata)


def find_imsi_from_pkt(p):
    udpdata = bytes(p[UDP].payload)
    find_imsi(udpdata)


def encode_imsi_filter(imsi_value):
    if not imsi_value:
        return ""

    encoded_imsi = ""
    imsi = "9" + imsi_value.replace(" ", "")
    imsi_to_track_len = len(imsi)
    if imsi_to_track_len % 2 == 0 and imsi_to_track_len > 0 and imsi_to_track_len < 17:
        for i in range(0, imsi_to_track_len - 1, 2):
            encoded_imsi += chr(int(imsi[i + 1]) * 16 + int(imsi[i]))
        return encoded_imsi

    raise ValueError("Wrong size for the IMSI to track")


if __name__ == "__main__":
    imsitracker = tracker()
    parser = OptionParser(usage="%prog: [options]")
    parser.add_option("-a", "--alltmsi", action="store_true", dest="show_all_tmsi", help="Show TMSI who haven't got IMSI (default  : false)")
    parser.add_option("-i", "--iface", dest="iface", default="lo", help="Interface (default : lo)")
    parser.add_option("-m", "--imsi", dest="imsi", default="", type="string", help='IMSI to track (default : None, Example: 123456789101112 or "123 45 6789101112")')
    parser.add_option("-p", "--port", dest="port", default="4729", type="int", help="Port (default : 4729)")
    parser.add_option("-s", "--sniff", action="store_true", dest="sniff", help="sniff on interface instead of listening on port (require root/suid access)")
    parser.add_option("-w", "--sqlite", dest="sqlite", default=None, type="string", help="Save observed IMSI values to specified SQLite file")
    parser.add_option("-t", "--txt", dest="txt", default=None, type="string", help="Save observed IMSI values to specified CSV file")
    parser.add_option("-z", "--mysql", action="store_true", dest="mysql", help="Save observed IMSI values to specified MYSQL DB (copy .env.dist to .env and edit it)")
    parser.add_option("-f", "--format", dest="output_format", default="table", type="string", help="Output format: table, csv, or json (default: table)")
    parser.add_option("--show-meta", action="store_true", dest="show_meta", help="Show packet metadata columns such as ARFCN, timeslot, signal level, SNR, frame number, and cell state")
    (options, args) = parser.parse_args()

    if options.output_format not in ("table", "csv", "json"):
        print("Wrong value for --format. Valid values: table, csv, json")
        sys.exit(1)

    if options.output_format == "csv":
        options.show_meta = True

    if options.sqlite:
        imsitracker.sqlite_file(options.sqlite)

    if options.txt:
        imsitracker.text_file(options.txt)

    if options.mysql:
        imsitracker.mysql_file()

    imsitracker.set_output_format(options.output_format, show_meta=options.show_meta)
    imsitracker.show_all_tmsi = options.show_all_tmsi
    imsi_to_track = ""
    if options.imsi:
        try:
            imsi_to_track = encode_imsi_filter(options.imsi)
        except ValueError:
            print("Wrong size for the IMSI to track!")
            print("Valid sizes :")
            print("123456789101112")
            print("1234567891011")
            print("12345678910")
            print("123456789")
            print("1234567")
            print("12345")
            print("123")
            exit(1)
    imsitracker.track_this_imsi(imsi_to_track)
    if options.sniff:
        from scapy.all import sniff, UDP
        imsitracker.header()
        sniff(iface=options.iface, filter=f"port {options.port} and not icmp and udp", prn=find_imsi_from_pkt, store=0)
    else:
        imsitracker.header()
        udpserver(port=options.port, prn=find_imsi)
