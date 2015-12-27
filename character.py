#!/usr/bin/python3

import math
from fractions import Fraction
import parsedatetime
import time
import collections
import heapq

#GENERIC_CHANGE_MESSAGE

def log(*args,**kwargs):
	pass
#log = print


def nth_pyramid_number(n):
	return (n*(n+1))/2

def which_pyramid_number_is(t):
	return (math.sqrt(8*t+1) - 1)/2

def cp_to_level(cp,cpl=1,pyramidal=False):
	if pyramidal:
		if cpl > 1:
			# Pyramiding starts at the /second/ level. First level always just 1.
			# So subtract 1 from CP.
			if cp==0:
				return 0
			if cp==1:
				return 1
			# Not counting that first CP, and counting each CPL CP as 1CP,
			# and then adding back in the level from the first CP...
			return int(which_pyramid_number_is((cp-1)/cpl)) + 1
		else:
			return int(which_pyramid_number_is(cp))
	else:
		return int(math.ceil(cp / cpl))

def level_to_cp(level,cpl=1,pyramidal=False):
	if pyramidal:
		if cpl > 1:
			# Again, first level cost 1CP, and /then/ CPL+pyramiding come into
			# play.
			if not level:
				return 0
			if level == 1:
				return 1
			return (nth_pyramid_number(level-1)*cpl) + 1
		else:
			return nth_pyramid_number(level)
	else:
		return (cpl*(level-1)+1) 

Notification = collections.namedtuple("Notification","image message")
SelectedStorylet = collections.namedtuple("SelectedStorylet","storylet failed_requirements")

def level_change_notification(quality, level):
	levels = quality.levels
	upstack_quality = quality
	while not levels and upstack_quality.template.dereference():
		upstack_quality = upstack_quality.template.dereference()
		levels = upstack_quality.levels
	change_messages = sorted([l for l in quality.levels if l.value <= level], key=(lambda q: q.value))
	if not change_messages:
		if level:
			return Notification(quality.image, "You now have %dx %s."%(level, quality.name))
		else:
			return Notification(quality.image, "You no longer have any %s."%(level, quality.name))
	image = change_messages[-1].changetext.image or change_messages[-1].image or quality.image
	upstack_quality = quality
	while not image and upstack_quality.template.dereference():
		upstack_quality = upstack_quality.template.dereference()
		image = upstack_quality.image
	return Notification(image, change_messages[-1].changetext.body.format(quality=quality.name, level_desc=change_messages[-1].description, level=level))

def cp_change_notification(quality, by=0):
	levels = quality.levels
	upstack_quality = quality
	while not levels and upstack_quality.template.dereference():
		upstack_quality = upstack_quality.template.dereference()
		levels = upstack_quality.levels
	change_messages = sorted([l for l in quality.levels if l.value <= level], key=(lambda q: q.value))
	image = change_messages[-1].image or quality.image
	upstack_quality = quality
	while not image and upstack_quality.template.dereference():
		upstack_quality = upstack_quality.template.dereference()
		image = upstack_quality.image
	return Notification(image, "%s is %s..."%(quality.name, "increasing" if by>0 else "decreasing"))

def event_scheduled_notification(event):
	return Notification(event.image, event.warning or "Something's been set in motion.")

class Character:
	def __init__(self, world, traits = None, event_delegate = None):
		self.world = world
		self.event_delegate = None
		if traits is None:
			self.qualities = collections.defaultdict(lambda:0)
			self.pending_event_heap = []
			self.setting = None
			self.area = None
			self.apply_outcomes(world.initial.sets)
			self.apply_outcomes([world.initial.moveto])
			self.cards = []
		else:
			self.qualities = collections.defaultdict(lambda:0, traits['qualities'])
			if traits['events']:
				events = {event.id:event for event in world.events}
				self.pending_event_heap = [(q[0], events[q[1]]) for q in traits['events']]
			else:
				self.pending_event_heap = []
			self.setting = traits['setting']
			self.area = traits['area']
			if traits['cards']:
				storylets = {storylet.id:storylet for storylet in world.storylets}
				self.cards = [storylets[q] for q in traits['cards']]
			else:
				self.cards = []
		self.event_delegate = event_delegate
	def traits(self):
		return {
			'qualities':dict(self.qualities),
			'events':[(q[0],q[1].id) for q in self.pending_event_heap],
			'setting':self.setting,
			'area':self.area
		}
	def qualifies_for(self, requirement):
		value = self.qualities[requirement.quality.dereference().id]
		if requirement.min is not None and requirement.min > value:
			log('\tquality %s = %d but must be >= %d'%(requirement.quality.dereference().id, value, requirement.min))
			return False
		if requirement.max is not None and requirement.max < value:
			log('\tquality %s = %d but must be <= %d'%(requirement.quality.dereference().id, value, requirement.max))
			return False
		# TODO: advanced?
		log('\tquality %s (=%d) looks good'%(requirement.quality.dereference().id,value))
		return True
		
	def eligible_storylets(self):
		if not self.world.alwaysdeck:
			return
		if not self.world.alwaysdeck.dereference():
			return
		
		storylets = [card.storylet.dereference() for card in self.world.alwaysdeck.dereference().cards if card.storylet.dereference() is not None]
		for storylet in storylets:
			log('can we play `%s`?'%(storylet.id))
			if storylet.location:
				setting = storylet.location.setting
				if setting is not None and setting.dereference() != self.setting:
					log("\twe have to be in %s but we're in %s"%(setting.dereference(),self.setting))
					continue
				area = storylet.location.area
				if area is not None and area.dereference() != self.area:
					log("\twe have to be in %s but we're in %s"%(area.dereference(),self.area))
					continue
			failed_requirements = []
			for requirement in storylet.requirements:
				if not self.qualifies_for(requirement):
					failed_requirements.append(requirement)
					if not requirement.vwrf:
						break
			else:
				log('...passback')
				# Qualified for all requirements, or failed with VWRF=true
				yield storylet
			
	def register_event(self, event):
		if self.event_delegate:
			event_delegate(event)
	def drain_pending_events(self):
		while self.pending_event_heap and self.pending_event_heap[0][0] > time.time():
			yield heapq.heappop(self.pending_event_heap)[1]
	def apply_outcomes(self, outcomes):
		for outcome in outcomes:
			if outcome.tag_name == 'set':
				quality = outcome.quality.dereference()
				if quality is None:
					# TODO: real error msg
					raise NotImplementedError()
				else:
					if cp_to_level(self.qualities[quality.id],quality.cpl,quality.pyramidal) != outcome.to:
						new_cp_value = level_to_cp(outcome.to,quality.cpl,quality.pyramidal)
						self.qualities[quality.id] = new_cp_value
						self.register_event(level_change_notification(quality, level))
			if outcome.tag_name == 'change':
				quality = outcome.quality.dereference()
				if quality is None:
					# TODO: real error msg
					raise NotImplementedError()
				else:
					if cp_to_level(self.qualities[quality.id]+outcome.by,quality.cpl,quality.pyramidal) == cp_to_level(self.qualities[quality.id],quality.cpl,quality.pyramidal):
						self.register_event(cp_change_notification(quality, outcome.by))
					else:
						self.register_event(level_change_notification(quality, level))
					self.qualities[quality.id] += outcome.by
					if self.qualities[quality.id] < 0:
						self.qualities[quality.id] = 0
			if outcome.tag_name == 'moveto':
				new_setting = self.setting
				new_area = self.area
				if outcome.setting:
					setting = outcome.setting.dereference()
					if setting is None:
						# TODO: real error msg
						raise NotImplementedError()
					else:
						new_setting = setting
						
				if outcome.area:
					area = outcome.area.dereference()
					if area is None:
						# TODO: real error msg
						raise NotImplementedError()
					else:
						new_area = area
				if new_area not in new_setting.areas:
					# TODO
					raise NotImplementedError()
				if new_area != self.area:
					self.area = new_area
					self.setting = new_setting
			if outcome.tag_name == 'schedule':
				event = schedule.event.dereference()
				if not event:
					# TODO
					raise NotImplementedError()
				when, was_parsed = parsedatetime.Calendar().parse(event.after)
				if not was_parsed:
					# TODO
					raise NotImplementedError()
				heapq.heappush(self.pending_event_heap,(time.mktime(event), event))
				self.register_event(event_scheduled_notification(event))
