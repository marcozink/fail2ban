# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: t -*-
# vi: set ft=python sts=4 ts=4 sw=4 noet :

# This file is part of Fail2Ban.
#
# Fail2Ban is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Fail2Ban is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Fail2Ban; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

# Fail2Ban developers

__copyright__ = "Copyright (c) 2013 Steven Hiscocks"
__license__ = "GPL"

import os
import sys
import unittest
import tempfile
import sqlite3
import shutil

from ..server.filter import FileContainer
from ..server.mytime import MyTime
from ..server.ticket import FailTicket
from .dummyjail import DummyJail
try:
	from ..server.database import Fail2BanDb
except ImportError:
	Fail2BanDb = None

TEST_FILES_DIR = os.path.join(os.path.dirname(__file__), "files")

class DatabaseTest(unittest.TestCase):

	def setUp(self):
		"""Call before every test case."""
		if Fail2BanDb is None and sys.version_info >= (2,7): # pragma: no cover
			raise unittest.SkipTest(
				"Unable to import fail2ban database module as sqlite is not "
				"available.")
		elif Fail2BanDb is None:
			return
		_, self.dbFilename = tempfile.mkstemp(".db", "fail2ban_")
		self.db = Fail2BanDb(self.dbFilename)

	def tearDown(self):
		"""Call after every test case."""
		if Fail2BanDb is None: # pragma: no cover
			return
		# Cleanup
		os.remove(self.dbFilename)

	def testGetFilename(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.assertEqual(self.dbFilename, self.db.filename)

	def testCreateInvalidPath(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.assertRaises(
			sqlite3.OperationalError,
			Fail2BanDb,
			"/this/path/should/not/exist")

	def testCreateAndReconnect(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail()
		# Reconnect...
		self.db = Fail2BanDb(self.dbFilename)
		# and check jail of same name still present
		self.assertTrue(
			self.jail.name in self.db.getJailNames(),
			"Jail not retained in Db after disconnect reconnect.")

	def testUpdateDb(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		shutil.copyfile(
			os.path.join(TEST_FILES_DIR, 'database_v1.db'), self.dbFilename)
		self.db = Fail2BanDb(self.dbFilename)
		self.assertEqual(self.db.getJailNames(), set(['DummyJail #29162448 with 0 tickets']))
		self.assertEqual(self.db.getLogPaths(), set(['/tmp/Fail2BanDb_pUlZJh.log']))
		ticket = FailTicket("127.0.0.1", 1388009242.26, [u"abc\n"])
		self.assertEqual(self.db.getBans()[0], ticket)

		self.assertEqual(self.db.updateDb(Fail2BanDb.__version__), Fail2BanDb.__version__)
		self.assertRaises(NotImplementedError, self.db.updateDb, Fail2BanDb.__version__ + 1)
		os.remove(self.db._dbBackupFilename)

	def testAddJail(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.jail = DummyJail()
		self.db.addJail(self.jail)
		self.assertTrue(
			self.jail.name in self.db.getJailNames(),
			"Jail not added to database")

	def testAddLog(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail() # Jail required

		_, filename = tempfile.mkstemp(".log", "Fail2BanDb_")
		self.fileContainer = FileContainer(filename, "utf-8")

		self.db.addLog(self.jail, self.fileContainer)

		self.assertTrue(filename in self.db.getLogPaths(self.jail))
		os.remove(filename)

	def testUpdateLog(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddLog() # Add log file

		# Write some text
		filename = self.fileContainer.getFileName()
		file_ = open(filename, "w")
		file_.write("Some text to write which will change md5sum\n")
		file_.close()
		self.fileContainer.open()
		self.fileContainer.readline()
		self.fileContainer.close()

		# Capture position which should be after line just written
		lastPos = self.fileContainer.getPos()
		self.assertTrue(lastPos > 0)
		self.db.updateLog(self.jail, self.fileContainer)

		# New FileContainer for file
		self.fileContainer = FileContainer(filename, "utf-8")
		self.assertEqual(self.fileContainer.getPos(), 0)

		# Database should return previous position in file
		self.assertEqual(
			self.db.addLog(self.jail, self.fileContainer), lastPos)

		# Change md5sum
		file_ = open(filename, "w") # Truncate
		file_.write("Some different text to change md5sum\n")
		file_.close()

		self.fileContainer = FileContainer(filename, "utf-8")
		self.assertEqual(self.fileContainer.getPos(), 0)

		# Database should be aware of md5sum change, such doesn't return
		# last position in file
		self.assertEqual(
			self.db.addLog(self.jail, self.fileContainer), None)
		os.remove(filename)

	def testAddBan(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail()
		ticket = FailTicket("127.0.0.1", 0, ["abc\n"])
		self.db.addBan(self.jail, ticket)

		self.assertEqual(len(self.db.getBans(jail=self.jail)), 1)
		self.assertTrue(
			isinstance(self.db.getBans(jail=self.jail)[0], FailTicket))

	def testGetBansWithTime(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail()
		self.db.addBan(
			self.jail, FailTicket("127.0.0.1", MyTime.time() - 60, ["abc\n"]))
		self.db.addBan(
			self.jail, FailTicket("127.0.0.1", MyTime.time() - 40, ["abc\n"]))
		self.assertEqual(len(self.db.getBans(jail=self.jail,bantime=50)), 1)
		self.assertEqual(len(self.db.getBans(jail=self.jail,bantime=20)), 0)
		# Negative values are for persistent bans, and such all bans should
		# be returned
		self.assertEqual(len(self.db.getBans(jail=self.jail,bantime=-1)), 2)

	def testGetBansMerged(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail()

		jail2 = DummyJail()
		self.db.addJail(jail2)

		ticket = FailTicket("127.0.0.1", MyTime.time() - 40, ["abc\n"])
		ticket.setAttempt(10)
		self.db.addBan(self.jail, ticket)
		ticket = FailTicket("127.0.0.1", MyTime.time() - 30, ["123\n"])
		ticket.setAttempt(20)
		self.db.addBan(self.jail, ticket)
		ticket = FailTicket("127.0.0.2", MyTime.time() - 20, ["ABC\n"])
		ticket.setAttempt(30)
		self.db.addBan(self.jail, ticket)
		ticket = FailTicket("127.0.0.1", MyTime.time() - 10, ["ABC\n"])
		ticket.setAttempt(40)
		self.db.addBan(jail2, ticket)

		# All for IP 127.0.0.1
		ticket = self.db.getBansMerged("127.0.0.1")
		self.assertEqual(ticket.getIP(), "127.0.0.1")
		self.assertEqual(ticket.getAttempt(), 70)
		self.assertEqual(ticket.getMatches(), ["abc\n", "123\n", "ABC\n"])

		# All for IP 127.0.0.1 for single jail
		ticket = self.db.getBansMerged("127.0.0.1", jail=self.jail)
		self.assertEqual(ticket.getIP(), "127.0.0.1")
		self.assertEqual(ticket.getAttempt(), 30)
		self.assertEqual(ticket.getMatches(), ["abc\n", "123\n"])

		# Should cache result if no extra bans added
		self.assertEqual(
			id(ticket),
			id(self.db.getBansMerged("127.0.0.1", jail=self.jail)))

		newTicket = FailTicket("127.0.0.2", MyTime.time() - 20, ["ABC\n"])
		ticket.setAttempt(40)
		# Add ticket, but not for same IP, so cache still valid
		self.db.addBan(self.jail, newTicket)
		self.assertEqual(
			id(ticket),
			id(self.db.getBansMerged("127.0.0.1", jail=self.jail)))

		newTicket = FailTicket("127.0.0.1", MyTime.time() - 10, ["ABC\n"])
		ticket.setAttempt(40)
		self.db.addBan(self.jail, newTicket)
		# Added ticket, so cache should have been cleared
		self.assertNotEqual(
			id(ticket),
			id(self.db.getBansMerged("127.0.0.1", jail=self.jail)))

		tickets = self.db.getBansMerged()
		self.assertEqual(len(tickets), 2)
		self.assertEqual(
			sorted(list(set(ticket.getIP() for ticket in tickets))),
			sorted([ticket.getIP() for ticket in tickets]))

		tickets = self.db.getBansMerged(jail=jail2)
		self.assertEqual(len(tickets), 1)

		tickets = self.db.getBansMerged(bantime=25)
		self.assertEqual(len(tickets), 2)
		tickets = self.db.getBansMerged(bantime=15)
		self.assertEqual(len(tickets), 1)
		tickets = self.db.getBansMerged(bantime=5)
		self.assertEqual(len(tickets), 0)
		# Negative values are for persistent bans, and such all bans should
		# be returned
		tickets = self.db.getBansMerged(bantime=-1)
		self.assertEqual(len(tickets), 2)

	def testPurge(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		self.testAddJail() # Add jail

		self.db.purge() # Jail enabled by default so shouldn't be purged
		self.assertEqual(len(self.db.getJailNames()), 1)

		self.db.delJail(self.jail)
		self.db.purge() # Should remove jail
		self.assertEqual(len(self.db.getJailNames()), 0)

		self.testAddBan()
		self.db.delJail(self.jail)
		self.db.purge() # Purge should remove all bans
		self.assertEqual(len(self.db.getJailNames()), 0)
		self.assertEqual(len(self.db.getBans(jail=self.jail)), 0)

		# Should leave jail
		self.testAddJail()
		self.db.addBan(
			self.jail, FailTicket("127.0.0.1", MyTime.time(), ["abc\n"]))
		self.db.delJail(self.jail)
		self.db.purge() # Should leave jail as ban present
		self.assertEqual(len(self.db.getJailNames()), 1)
		self.assertEqual(len(self.db.getBans(jail=self.jail)), 1)


# Author: Serg G. Brester (sebres)
# 

__author__ = "Serg Brester"
__copyright__ = "Copyright (c) 2014 Serg G. Brester"

class BanTimeIncr(unittest.TestCase):

	def setUp(self):
		"""Call before every test case."""
		if Fail2BanDb is None and sys.version_info >= (2,7): # pragma: no cover
			raise unittest.SkipTest(
				"Unable to import fail2ban database module as sqlite is not "
				"available.")
		elif Fail2BanDb is None:
			return
		_, self.dbFilename = tempfile.mkstemp(".db", "fail2ban_")
		self.db = Fail2BanDb(self.dbFilename)

	def tearDown(self):
		"""Call after every test case."""
		if Fail2BanDb is None: # pragma: no cover
			return
		# Cleanup
		os.remove(self.dbFilename)

	def testBanTimeIncr(self):
		if Fail2BanDb is None: # pragma: no cover
			return
		jail = DummyJail()
		jail.database = self.db
		self.db.addJail(jail)
		a = jail.actions
		# we tests with initial ban time = 10 seconds:
		a.setBanTime(10)
		a.setBanTimeExtra('enabled', 'true')
		a.setBanTimeExtra('multipliers', '1 2 4 8 16 32 64 128 256 512 1024 2048')
		ip = "127.0.0.2"
		# used as start and fromtime (like now but time independence, cause test case can run slow):
		stime = int(MyTime.time())
		ticket = FailTicket(ip, stime, [])
		# test ticket not yet found
		self.assertEqual(
			[a.incrBanTime(ticket) for i in xrange(3)], 
			[10, 10, 10]
		)
		# add a ticket banned
		self.db.addBan(jail, ticket)
		# get a ticket already banned in this jail:
		self.assertEqual(
			[(banCount, timeOfBan, lastBanTime) for banCount, timeOfBan, lastBanTime in self.db.getBan(ip, jail, None, False)],
			[(1, stime, 10)]
		)
		# incr time and ban a ticket again :
		ticket.setTime(stime + 15)
		self.assertEqual(a.incrBanTime(ticket), 20)
		self.db.addBan(jail, ticket)
		# get a ticket already banned in this jail:
		self.assertEqual(
			[(banCount, timeOfBan, lastBanTime) for banCount, timeOfBan, lastBanTime in self.db.getBan(ip, jail, None, False)],
			[(2, stime + 15, 20)]
		)
		# get a ticket already banned in all jails:
		self.assertEqual(
			[(banCount, timeOfBan, lastBanTime) for banCount, timeOfBan, lastBanTime in self.db.getBan(ip, '', None, True)],
			[(2, stime + 15, 20)]
		)
		# search currently banned and 1 day later (nothing should be found):
		self.assertEqual(
			self.db.getCurrentBans(forbantime=-24*60*60, fromtime=stime),
			[]
		)
		# search currently banned anywhere:
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(
			str(restored_tickets),
			('[FailTicket: ip=%s time=%s bantime=20 bancount=2 #attempts=0 matches=[]]' % (ip, stime + 15))
		)
		# search currently banned:
		restored_tickets = self.db.getCurrentBans(jail=jail, fromtime=stime)
		self.assertEqual(
			str(restored_tickets), 
			('[FailTicket: ip=%s time=%s bantime=20 bancount=2 #attempts=0 matches=[]]' % (ip, stime + 15))
		)
		restored_tickets[0].setRestored(True)
		self.assertTrue(restored_tickets[0].getRestored())
		# increase ban multiple times:
		lastBanTime = 20
		for i in xrange(10):
			ticket.setTime(stime + lastBanTime + 5)
			banTime = a.incrBanTime(ticket)
			self.assertEqual(banTime, lastBanTime * 2)
			self.db.addBan(jail, ticket)
			lastBanTime = banTime
		# increase again, but the last multiplier reached (time not increased):
		ticket.setTime(stime + lastBanTime + 5)
		banTime = a.incrBanTime(ticket)
		self.assertNotEqual(banTime, lastBanTime * 2)
		self.assertEqual(banTime, lastBanTime)
		self.db.addBan(jail, ticket)
		lastBanTime = banTime
		# add two tickets from yesterday: one unbanned (bantime already out-dated):
		ticket2 = FailTicket(ip+'2', stime-24*60*60, [])
		ticket2.setBanTime(12*60*60)
		self.db.addBan(jail, ticket2)
		# and one from yesterday also, but still currently banned :
		ticket2 = FailTicket(ip+'1', stime-24*60*60, [])
		ticket2.setBanTime(36*60*60)
		self.db.addBan(jail, ticket2)
		# search currently banned:
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(len(restored_tickets), 2)
		self.assertEqual(
			str(restored_tickets[0]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=13 #attempts=0 matches=[]' % (ip, stime + lastBanTime + 5, lastBanTime)
		)
		self.assertEqual(
			str(restored_tickets[1]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=1 #attempts=0 matches=[]' % (ip+'1', stime-24*60*60, 36*60*60)
		)
		# search out-dated (give another fromtime now is -18 hours):
		restored_tickets = self.db.getCurrentBans(fromtime=stime-18*60*60)
		self.assertEqual(len(restored_tickets), 3)
		self.assertEqual(
			str(restored_tickets[2]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=1 #attempts=0 matches=[]' % (ip+'2', stime-24*60*60, 12*60*60)
		)
		# should be still banned
		self.assertFalse(restored_tickets[1].isTimedOut(stime))
		self.assertFalse(restored_tickets[1].isTimedOut(stime))
		# the last should be timed out now
		self.assertTrue(restored_tickets[2].isTimedOut(stime))
		self.assertFalse(restored_tickets[2].isTimedOut(stime-18*60*60))

		# test permanent, create timed out:
		ticket=FailTicket(ip+'3', stime-36*60*60, [])
		self.assertTrue(ticket.isTimedOut(stime, 600))
		# not timed out - permanent jail:
		self.assertFalse(ticket.isTimedOut(stime, -1))
		# not timed out - permanent ticket:
		ticket.setBanTime(-1)
		self.assertFalse(ticket.isTimedOut(stime, 600))
		self.assertFalse(ticket.isTimedOut(stime, -1))
		# timed out - permanent jail but ticket time (not really used behavior)
		ticket.setBanTime(600)
		self.assertTrue(ticket.isTimedOut(stime, -1))

		# get currently banned pis with permanent one:
		ticket.setBanTime(-1)
		self.db.addBan(jail, ticket)
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(len(restored_tickets), 3)
		self.assertEqual(
			str(restored_tickets[2]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=1 #attempts=0 matches=[]' % (ip+'3', stime-36*60*60, -1)
		)
		# purge (nothing should be changed):
		self.db.purge()
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(len(restored_tickets), 3)
		# set short time and purge again:
		ticket.setBanTime(600)
		self.db.addBan(jail, ticket)
		self.db.purge()
		# this old ticket should be removed now:
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(len(restored_tickets), 2)
		self.assertEqual(restored_tickets[0].getIP(), ip)

    # purge remove 1st ip
		self.db._purgeAge = -48*60*60
		self.db.purge()
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(len(restored_tickets), 1)
		self.assertEqual(restored_tickets[0].getIP(), ip+'1')

    # this should purge all bans, bips and logs - nothing should be found now
		self.db._purgeAge = -240*60*60
		self.db.purge()
		restored_tickets = self.db.getCurrentBans(fromtime=stime)
		self.assertEqual(restored_tickets, [])

    # two separate jails :
		jail1 = DummyJail()
		jail1.database = self.db
		self.db.addJail(jail1)
		jail2 = DummyJail()
		jail2.database = self.db
		self.db.addJail(jail2)
		ticket1 = FailTicket(ip, stime, [])
		ticket1.setBanTime(6000)
		self.db.addBan(jail1, ticket1)
		ticket2 = FailTicket(ip, stime-6000, [])
		ticket2.setBanTime(12000)
		ticket2.setBanCount(1)
		self.db.addBan(jail2, ticket2)
		restored_tickets = self.db.getCurrentBans(jail=jail1, fromtime=stime)
		self.assertEqual(len(restored_tickets), 1)
		self.assertEqual(
			str(restored_tickets[0]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=1 #attempts=0 matches=[]' % (ip, stime, 6000)
		)
		restored_tickets = self.db.getCurrentBans(jail=jail2, fromtime=stime)
		self.assertEqual(len(restored_tickets), 1)
		self.assertEqual(
			str(restored_tickets[0]),
			'FailTicket: ip=%s time=%s bantime=%s bancount=2 #attempts=0 matches=[]' % (ip, stime-6000, 12000)
		)
    # get last ban values for this ip separately for each jail:
		for row in self.db.getBan(ip, jail1):
			self.assertEqual(row, (1, stime, 6000))
			break
		for row in self.db.getBan(ip, jail2):
			self.assertEqual(row, (2, stime-6000, 12000))
			break
    # get max values for this ip (over all jails):
		for row in self.db.getBan(ip, overalljails=True):
			self.assertEqual(row, (3, stime, 18000))
			break
