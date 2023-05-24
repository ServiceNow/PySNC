from unittest import TestCase
from pysnc.record import GlideElement, GlideRecord
import datetime, json, re


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
        self.assertEqual(repr(element), "GlideElement('4')")
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

    def test_serialization(self):
        gr = GlideRecord(None, 'incident')
        gr.initialize()
        gr.test_field = 'some string'
        self.assertTrue(isinstance(gr.test_field, GlideElement))
        r = gr.serialize()
        self.assertEqual(json.dumps(r), '{"test_field": "some string"}')

        gr.set_value('test_field', 'somevalue')
        gr.set_display_value('test_field', 'Some Value')
        print(gr.serialize())
        self.assertEqual(json.dumps(gr.serialize()), '{"test_field": "somevalue"}')
        self.assertEqual(json.dumps(gr.serialize(display_value=True)), '{"test_field": "Some Value"}')
        self.assertEqual(json.dumps(gr.serialize(display_value='both')), '{"test_field": {"value": "somevalue", "display_value": "Some Value"}}')

        # but what if we set a element to an element
        gr2 = GlideRecord(None, 'incident')
        gr2.initialize()
        gr2.two_field = gr.test_field
        self.assertEqual(json.dumps(gr2.serialize()), '{"two_field": "somevalue"}')
        self.assertEqual(json.dumps(gr2.serialize(display_value=True)), '{"two_field": "Some Value"}')
        self.assertEqual(gr2.two_field.get_name(), 'two_field')

    def test_set_element(self):
        element = GlideElement('state', '3', 'Pending Change')

        gr = GlideRecord(None, 'incident')
        gr.initialize()
        gr.state = '3'
        out1 = gr.serialize()
        print(out1)
        gr.initialize()
        gr.state = element
        out2 = gr.serialize()
        print(out2)
        self.assertEqual(out1, out2)

    def test_hashing(self):
        element = GlideElement('state', '3', 'Pending Change')
        my_dict = {}
        my_dict[element] = 1
        self.assertEqual(my_dict[element], 1)

    def test_int(self):
        element = GlideElement('state', '3', 'Pending Change')
        result = int(element)
        self.assertEqual(result, 3)

    def test_float(self):
        element = GlideElement('state', '3.1', 'Pending Change')
        result = float(element)
        self.assertEqual(result, 3.1)

    def test_complex(self):
        element = GlideElement('state', '5-9j', 'Pending Change')
        result = complex(element)
        self.assertEqual(result, 5-9j)

    def test_indexing(self):
        element = GlideElement('state', 'approved')
        self.assertEqual(element[0], 'a')
        self.assertEqual(element[-1], 'd')
        self.assertEqual(element[::-1], 'devorppa')

    def test_string_methods(self):
        element = GlideElement('state', 'approved Value')
        self.assertEqual(element.capitalize(), 'Approved value')
        self.assertEqual(element.casefold(), 'approved value')
        self.assertEqual(element.encode(), b'approved Value')
        self.assertEqual(element.isdigit(), False)
        self.assertEqual(element.islower(), False)
        self.assertEqual(element.isprintable(), True)

    def test_regex(self):
        from collections import UserString
        element = GlideElement('state', '3', 'Pending Change')
        result = re.match(r"\d", element)
        self.assertIsNotNone(result)
        self.assertEqual(result.start(), 0)
        self.assertEqual(result.end(), 1)
        self.assertEqual(result.group(), '3')

        element = GlideElement('state', 'ohh 3 okay', 'Pending Change')
        result = re.search(r"(\d)", element)
        self.assertIsNotNone(result)
        self.assertEqual(result.start(), 4)
        self.assertEqual(result.end(), 5)
        self.assertEqual(result.group(), '3')

    def test_parent(self):
        class MockRecord:
            def get_element(self, name):
                rn = name.split('.')[-1]
                return GlideElement(rn, 'test@test.test', None, self)
        opened_by = GlideElement('opened_by', 'somesysid', 'User Name', MockRecord())

        self.assertEqual(opened_by, 'somesysid')
        ele = opened_by.email
        self.assertEqual(ele, 'test@test.test')
        self.assertEqual(ele.get_name(), 'email')
        self.assertTrue(isinstance(ele._parent_record, MockRecord))
