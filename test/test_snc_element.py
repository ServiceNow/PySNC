from unittest import TestCase
from pysnc.record import GlideElement
import datetime


class TestElement(TestCase):


    def test_truefalse(self):
        element = GlideElement('active', 'true')
        self.assertTrue(bool(element))
        self.assertEqual(element, 'true')

        element = GlideElement('active', 'false')
        self.assertFalse(bool(element))
        self.assertEqual(element, 'false')

    def test_iter(self):
        element = GlideElement('active', 'abcd')
        self.assertEqual(element, 'abcd')
        self.assertEqual(len(element), 4)
        for e in element:
            self.assertIsNotNone(e)

        for l, r in zip(element, 'abcd'):
            self.assertEqual(l, r)

    def test_str(self):
        # https://docs.python.org/3/library/stdtypes.html#string-methods
        real_value = "A String! \N{SPARKLES}"
        display_value = "****"
        element = GlideElement('name', real_value, display_value)

        self.assertEqual(element, real_value)

        # they dont throw, we good
        element.casefold()
        self.assertIsNotNone(element.encode('utf-8'))
        self.assertFalse(element.islower())

        new_value = real_value + display_value
        self.assertIsNotNone(new_value)
        self.assertEqual(new_value, f"{real_value}{display_value}")

    def test_set_and_display(self):
        element = GlideElement('state', '3', 'Pending Change')
        self.assertEqual(element.get_display_value(), 'Pending Change')
        element.set_value('4')
        self.assertTrue(element.changes())
        self.assertIsNone(element._display_value)
        self.assertEqual(element.get_display_value(), '4')
        self.assertEqual(repr(element), "record.GlideElement(value='4', name='state', display_value=None, changed=True)")
        self.assertEqual(str(element), "4")

    def test_int(self):
        ten = GlideElement('num', 10)
        nten = GlideElement('negative_num', -10)

        print(GlideElement.__class__.__dict__)
        self.assertNotEqual(ten, 0)
        self.assertEqual(ten, 10)
        self.assertGreater(ten, 5)
        self.assertLess(ten, 15)
        self.assertGreaterEqual(ten, 10)
        self.assertLessEqual(ten, 10)
        self.assertTrue(ten)

        self.assertEqual(nten, -10)
        self.assertGreater(ten, nten)
        self.assertLess(nten, ten)

        self.assertEqual(ten + nten, 0)
        self.assertEqual(ten + 10, 20)
        self.assertEqual(ten - 10, 0)
        self.assertEqual(ten - nten, 20)

    def test_time(self):
        time = GlideElement('sys_created_on', '2007-07-03 18:48:47')
        # parse this into a known datetime
        same = datetime.datetime(2007, 7, 3, 18, 48, 47, tzinfo=datetime.timezone.utc)

        self.assertIsNotNone(time.date_value())
        self.assertEqual(time.date_value(), same)
        time_in_ms = 1183488527000
        self.assertEqual(time.date_numeric_value(), time_in_ms)
        dt = datetime.datetime.fromtimestamp(time_in_ms/1000.0, tz=datetime.timezone.utc)
        self.assertEqual(same, dt)
        time.set_date_numeric_value(1183488528000)
        self.assertEqual(time, '2007-07-03 18:48:48')

        time2 = GlideElement('sys_created_on', '2008-07-03 18:48:47')

        self.assertGreater(time2.date_value(), time.date_value())
        self.assertGreater(time2.date_numeric_value(), time.date_numeric_value())




