#!/usr/bin/env python3
import importlib.util
import os
import unittest

_spec = importlib.util.spec_from_file_location(
    "simple_imsi_catcher",
    os.path.join(os.path.dirname(__file__), "simple_IMSI-catcher.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


class TestDecodePlmn(unittest.TestCase):
    def test_2digit_mnc(self):
        # France MCC=208, MNC=20 (Bouygues)
        # octet1=0x02 (d2=0,d1=2), octet2=0xf8 (mnc_d3=0xf,mcc_d3=8), octet3=0x02 (mnc_d2=0,mnc_d1=2)
        mcc, mnc = _mod.decode_plmn(0x02, 0xf8, 0x02)
        self.assertEqual(mcc, "208")
        self.assertEqual(mnc, "20")

    def test_3digit_mnc(self):
        # US MCC=310, MNC=410 (AT&T)
        # octet1=0x13 (d2=1,d1=3), octet2=0x00 (mnc_d3=0,mcc_d3=0), octet3=0x14 (mnc_d2=1,mnc_d1=4)
        mcc, mnc = _mod.decode_plmn(0x13, 0x00, 0x14)
        self.assertEqual(mcc, "310")
        self.assertEqual(mnc, "410")

    def test_germany(self):
        # Germany MCC=262, MNC=01 (Telekom)
        mcc, mnc = _mod.decode_plmn(0x62, 0xf2, 0x10)
        self.assertEqual(mcc, "262")
        self.assertEqual(mnc, "01")

    def test_leading_zero_mcc_digit(self):
        # MCC=001 (Test network)
        mcc, mnc = _mod.decode_plmn(0x00, 0xf1, 0x00)
        self.assertEqual(mcc, "001")
        self.assertEqual(mnc, "00")


class TestStrTmsi(unittest.TestCase):
    def setUp(self):
        self.t = _mod.tracker()

    def test_from_docstring(self):
        result = self.t.str_tmsi(bytes([0xd9, 0x60, 0x54, 0x60]))
        self.assertEqual(result, "0xd9605460")

    def test_empty(self):
        self.assertEqual(self.t.str_tmsi(""), "")

    def test_single_byte_with_zero_nibble(self):
        self.assertEqual(self.t.str_tmsi(bytes([0x09])), "0x09")

    def test_single_byte_high_value(self):
        self.assertEqual(self.t.str_tmsi(bytes([0xff])), "0xff")

    def test_low_byte(self):
        # hex(0x0a) = '0xa' (len 3) → "0" + "a" = "0a"
        self.assertEqual(self.t.str_tmsi(bytes([0x0a])), "0x0a")


class TestDecodeImsi(unittest.TestCase):
    def setUp(self):
        self.t = _mod.tracker()

    def test_france_208_20(self):
        # IMSI "208201234567890" encoded as GSM semi-octets
        # Byte 0: parity=1/type=IMSI → low nibble 0x9, first digit 2 → 0x29
        # Byte 1: digits 0,8 → 0x80; ...
        imsi_bytes = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        raw, mcc, mnc = self.t.decode_imsi(imsi_bytes)
        self.assertEqual(mcc, "208")
        self.assertEqual(mnc, "20")
        self.assertEqual(raw, "9208201234567890")

    def test_mcc_mnc_extraction(self):
        # Verify mcc = raw[1:4], mnc = raw[4:6] for any input
        imsi_bytes = bytes([0x13, 0x00, 0x14, 0x00, 0x00, 0x00, 0x00, 0xf0])
        raw, mcc, mnc = self.t.decode_imsi(imsi_bytes)
        self.assertEqual(mcc, raw[1:4])
        self.assertEqual(mnc, raw[4:6])


class TestStrImsi(unittest.TestCase):
    def setUp(self):
        self.t = _mod.tracker()

    def test_known_operator(self):
        imsi_bytes = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        imsi_str, country, brand, operator = self.t.str_imsi(imsi_bytes)
        self.assertIn("208", imsi_str)
        self.assertIn("20", imsi_str)
        self.assertEqual(country, "France")
        self.assertEqual(brand, "Bouygues")
        self.assertIn("Bouygues", operator)

    def test_unknown_mcc(self):
        # MCC=999 almost certainly not in the database
        # Byte layout for 999/99: octet1=0x99, octet2=0xf9, octet3=0x99
        imsi_bytes = bytes([0x99, 0x99, 0x99, 0x00, 0x00, 0x00, 0x00, 0xf0])
        imsi_str, country, brand, operator = self.t.str_imsi(imsi_bytes)
        self.assertIn("Unknown", country)


class TestEncodeImsiFilter(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(_mod.encode_imsi_filter(""), b"")

    def test_none_like(self):
        self.assertEqual(_mod.encode_imsi_filter(None), b"")

    def test_mcc_prefix_208(self):
        result = _mod.encode_imsi_filter("208")
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 2)
        # "9208" → bytes: 2*16+9=0x29, 8*16+0=0x80
        self.assertEqual(result[0], 0x29)
        self.assertEqual(result[1], 0x80)

    def test_spaces_stripped(self):
        # "208 20" → "20820" → "920820" (6 chars, even)
        result = _mod.encode_imsi_filter("208 20")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], 0x29)
        self.assertEqual(result[1], 0x80)

    def test_full_15digit_imsi(self):
        result = _mod.encode_imsi_filter("208201234567890")
        self.assertEqual(len(result), 8)

    def test_invalid_even_digit_count_raises(self):
        with self.assertRaises(ValueError):
            _mod.encode_imsi_filter("1234")   # 4 digits → "91234" odd → invalid

    def test_invalid_too_long_raises(self):
        with self.assertRaises(ValueError):
            _mod.encode_imsi_filter("1234567890123456")  # 16 digits → 17 chars → invalid

    def test_filter_matches_imsi_bytes(self):
        # encode_imsi_filter("208") must byte-match the prefix of IMSI "208201234567890"
        filt = _mod.encode_imsi_filter("208")
        imsi_bytes = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.assertEqual(filt, imsi_bytes[:len(filt)])


class TestTrackerRegisterImsi(unittest.TestCase):
    def setUp(self):
        self.t = _mod.tracker()
        self.t.current_cell("208", "20", 412, 24989, arfcn=975)
        self.events = []
        self.t.set_output_function(lambda *a, **kw: self.events.append((a, kw)))

    def test_new_imsi_increments_counter(self):
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(self.t.nb_IMSI, 1)
        self.assertEqual(len(self.t.imsis), 1)

    def test_duplicate_imsi_not_counted_twice(self):
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.t.register_imsi(975, imsi1=imsi)
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(self.t.nb_IMSI, 1)

    def test_two_different_imsis(self):
        imsi1 = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        imsi2 = bytes([0x19, 0x62, 0x02, 0x21, 0x43, 0x65, 0x87, 0xf0])
        self.t.register_imsi(975, imsi1=imsi1)
        self.t.register_imsi(975, imsi1=imsi2)
        self.assertEqual(self.t.nb_IMSI, 2)

    def test_output_fired_for_new_imsi(self):
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(len(self.events), 1)

    def test_output_not_fired_for_duplicate(self):
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.t.register_imsi(975, imsi1=imsi)
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(len(self.events), 1)

    def test_imsi_filter_blocks_non_matching(self):
        filt = _mod.encode_imsi_filter("262")  # German MCC
        self.t.track_this_imsi(filt)
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])  # France 208
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(self.t.nb_IMSI, 0)

    def test_imsi_filter_passes_matching(self):
        filt = _mod.encode_imsi_filter("208")
        self.t.track_this_imsi(filt)
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])  # France 208
        self.t.register_imsi(975, imsi1=imsi)
        self.assertEqual(self.t.nb_IMSI, 1)

    def test_tmsi_only_not_counted_as_imsi(self):
        tmsi = bytes([0xd9, 0x60, 0x54, 0x60])
        self.t.register_imsi(975, tmsi1=tmsi)
        self.assertEqual(self.t.nb_IMSI, 0)

    def test_duplicate_imsi_with_new_tmsi_no_extra_output(self):
        # The tmsis dict is empty by default, so re-registering a known IMSI with
        # a different TMSI produces no additional output (TMSI updates only apply
        # when tmsis is already seeded, e.g. via show_all_tmsi mode).
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        self.t.register_imsi(975, imsi1=imsi, tmsi1=bytes([0xd9, 0x60, 0x54, 0x60]))
        count_before = len(self.events)
        self.t.register_imsi(975, imsi1=imsi, tmsi1=bytes([0xaa, 0xbb, 0xcc, 0xdd]))
        self.assertEqual(len(self.events), count_before)


class TestImsiPurge(unittest.TestCase):
    def test_old_entries_purged(self):
        import datetime
        t = _mod.tracker()
        t.purgeTimer = 0  # expire anything with lastseen strictly before "now"
        imsi = bytes([0x29, 0x80, 0x02, 0x21, 0x43, 0x65, 0x87, 0x09])
        t.imsi_seen(imsi, 975)
        raw, _, _ = t.decode_imsi(imsi)
        # Backdate the entry so it sits in the past (purgeTimer=0 → limit=now)
        t.imsistate[raw]["lastseen"] -= datetime.timedelta(seconds=1)
        self.assertEqual(len(t.imsistate), 1)
        # Seeing another IMSI triggers the purge pass
        t.imsi_seen(bytes([0x19, 0x62, 0x02, 0x21, 0x43, 0x65, 0x87, 0xf0]), 975)
        self.assertNotIn(raw, t.imsistate)


class TestCurrentCell(unittest.TestCase):
    def test_cell_context_populated(self):
        t = _mod.tracker()
        t.current_cell("208", "20", 412, 24989, arfcn=975)
        ctx = t.cell_context_for_event(975)
        self.assertEqual(ctx["mcc"], "208")
        self.assertEqual(ctx["mnc"], "20")
        self.assertEqual(ctx["lac"], "412")
        self.assertEqual(ctx["cell"], "24989")
        self.assertEqual(ctx["cell_status"], "current")

    def test_stale_on_wrong_arfcn(self):
        t = _mod.tracker()
        t.current_cell("208", "20", 412, 24989, arfcn=975)
        ctx = t.cell_context_for_event(100)
        self.assertEqual(ctx["cell_status"], "stale")

    def test_unknown_before_any_cell(self):
        t = _mod.tracker()
        ctx = t.cell_context_for_event(975)
        self.assertEqual(ctx["cell_status"], "unknown")


if __name__ == "__main__":
    unittest.main()
