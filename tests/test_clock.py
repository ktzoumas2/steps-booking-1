"""§11 — time is supplied, and wall-clock time is not an instant."""

import datetime as dt
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from supervision.clock import (
    BERLIN,
    FixedClock,
    SystemClock,
    get_clock,
    iso_week,
    to_berlin,
    today_in_berlin,
    using_clock,
    wall_clock_to_instant,
    week_bounds,
)

UTC = dt.UTC


class WallClockTests(SimpleTestCase):
    """A 10:00 session stays at 10:00 across a DST change (§11, §15.1)."""

    def test_ten_oclock_is_ten_oclock_on_both_sides_of_dst(self):
        # Central European Summer Time starts on 29 March 2026.
        before = wall_clock_to_instant(dt.date(2026, 3, 28), dt.time(10, 0))
        after = wall_clock_to_instant(dt.date(2026, 3, 30), dt.time(10, 0))

        # The stored wall-clock reading is unchanged...
        self.assertEqual(to_berlin(before).hour, 10)
        self.assertEqual(to_berlin(after).hour, 10)
        # ...while the actual instants differ by the hour the clocks moved.
        self.assertEqual(before.astimezone(UTC).hour, 9)
        self.assertEqual(after.astimezone(UTC).hour, 8)

    def test_the_same_instant_reads_differently_elsewhere(self):
        instant = wall_clock_to_instant(dt.date(2026, 11, 3), dt.time(10, 0))
        in_kabul = instant.astimezone(ZoneInfo("Asia/Kabul"))
        self.assertEqual((in_kabul.hour, in_kabul.minute), (13, 30))

    def test_berlin_date_is_not_the_utc_date(self):
        # 23:30 UTC on 2 November is already the 3rd in Berlin.
        instant = dt.datetime(2026, 11, 2, 23, 30, tzinfo=UTC)
        self.assertEqual(today_in_berlin(instant), dt.date(2026, 11, 3))


class IsoWeekTests(SimpleTestCase):
    """Weeks are ISO weeks, Monday–Sunday, in Europe/Berlin (§2, §6.1)."""

    def test_week_can_belong_to_the_previous_year(self):
        # 1 January 2026 is a Thursday, so its ISO week starts in December 2025.
        self.assertEqual(iso_week(dt.date(2026, 1, 1)), (2026, 1))
        self.assertEqual(
            week_bounds(2026, 1), (dt.date(2025, 12, 29), dt.date(2026, 1, 4))
        )

    def test_monday_and_sunday_share_a_week_and_the_next_day_does_not(self):
        monday, sunday = week_bounds(2026, 45)
        self.assertEqual(monday.isoweekday(), 1)
        self.assertEqual(sunday.isoweekday(), 7)
        self.assertEqual(iso_week(monday), iso_week(sunday))
        self.assertNotEqual(iso_week(sunday + dt.timedelta(days=1)), (2026, 45))


class SuppliedClockTests(SimpleTestCase):
    """A test must be able to stand before, during and after a session at will."""

    def test_fixed_clock_moves_only_when_told(self):
        clock = FixedClock(wall_clock_to_instant(dt.date(2026, 11, 3), dt.time(9, 0)))
        start = clock.now()
        self.assertEqual(clock.now(), start)

        clock.advance(hours=2)
        self.assertEqual(clock.now() - start, dt.timedelta(hours=2))

    def test_fixed_clock_normalises_to_utc_and_rejects_naive_instants(self):
        clock = FixedClock(dt.datetime(2026, 11, 3, 10, 0, tzinfo=BERLIN))
        self.assertEqual(clock.now().tzinfo, UTC)
        self.assertEqual(clock.now().hour, 9)

        with self.assertRaises(ValueError):
            FixedClock(dt.datetime(2026, 11, 3, 10, 0))

    def test_using_clock_restores_the_previous_one(self):
        clock = FixedClock(dt.datetime(2026, 11, 3, 9, 0, tzinfo=UTC))
        with using_clock(clock):
            self.assertIs(get_clock(), clock)
        self.assertIsInstance(get_clock(), SystemClock)
