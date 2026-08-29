#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc de la DATE des videos (`inventaire_videos`) : le nom, ExifTool, jamais
le mtime. Sortie ASCII. Aucun NAS, aucun exiftool lance."""
import unittest
from datetime import datetime

import inventaire_videos as IV


def annee(ts):
    return datetime.fromtimestamp(ts).year if ts else None


class DateDuNom(unittest.TestCase):
    def test_samsung_et_whatsapp(self):
        self.assertEqual(annee(IV.date_du_nom('20240101_120000.mp4')), 2024)
        self.assertEqual(annee(IV.date_du_nom('VID-20210613-WA0008.mp4')), 2021)
        self.assertEqual(annee(IV.date_du_nom('20211224_201807.mp4')), 2021)
        self.assertEqual(annee(IV.date_du_nom('VID_20191105_101010.mov')), 2019)

    def test_ce_qui_n_est_pas_une_date(self):
        for n in ('Highlight001.mp4', 'IMG_1234.mp4', '20251301_000000.mp4',
                  '180328_Samsung.mp4', 'Sandra (54).MP4', '12345678901.mp4'):
            self.assertIsNone(IV.date_du_nom(n), n)

    def test_heure_locale_gardee(self):
        ts = IV.date_du_nom('20231231_235959.mp4')
        self.assertEqual(datetime.fromtimestamp(ts), datetime(2023, 12, 31, 23, 59, 59))


class DateExif(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(annee(IV.date_exif('2021:12:24 20:18:07')), 2021)
        self.assertEqual(annee(IV.date_exif('2021:12:24 20:18:07+01:00')), 2021)
        self.assertEqual(annee(IV.date_exif('2021:12:24T20:18:07Z')), 2021)

    def test_compteurs_a_zero_refuses(self):
        for v in ('1904:01:01 00:00:00', '1970:01:01 00:00:00', '0000:00:00 00:00:00', '', None, 12):
            self.assertIsNone(IV.date_exif(v), repr(v))


class Exiftool(unittest.TestCase):
    def test_sans_exe_ni_fichiers_rien(self):
        self.assertEqual(IV.dates_exiftool(None, ['x.mp4'], lambda s: None), {})
        self.assertEqual(IV.dates_exiftool('exiftool', [], lambda s: None), {})


if __name__ == '__main__':
    unittest.main()
