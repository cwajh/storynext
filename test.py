#!/usr/bin/python3
import metatemplate
from lxml import etree
import string
import character
import itertools
import re
import getch
import sys

with open('metatemplate.xml') as qq:
	template_doc = etree.parse(qq)
element_definitions = {}
metatemplate.build_element_definitions_from_metatemplate(template_doc.getroot(),element_definitions)
print('element definitions:')
print("\n".join(sorted(["%s(%s)"%(tag, ', '.join(arg.name for arg in element_definitions[tag].arguments)) for tag in element_definitions])))

element_classes = {tag:metatemplate.element_class_for_def(element_definitions[tag],element_definitions)  for tag in element_definitions}
StorynextElement = element_classes['storynext']


postprocessors = {}
def renamer(element, global_lookup):
	if element['name'] is None:
		element['name'] = string.capwords(element['id'])
def fix_world(world, global_lookup):
	if world['defaultdeck']:
		# add storylets in this file without a deck to the default deck
		default_deck = world['defaultdeck'].dereference()
		if default_deck:
			storylets_in_decks = set()
			for deck in world['decks']:
				for card in deck.cards:
					storylet = card.storylet.dereference()
					if storylet:
						storylets_in_decks.add(storylet.id)
			for storylet in world['storylets']:
				if storylet.id not in storylets_in_decks:
					new_card = etree.Element('card')
					new_card.set('storylet',storylet.id)
					default_deck.cards.append(element_classes['card'](
						lx_element = new_card,
						parent_id = default_deck.id,
						global_lookup = global_lookup,
						local_lookup={},
						class_directory = element_classes,
						postprocessors = postprocessors
						))
	# TODO: merge includes
		
postprocessors.update( {'deck':renamer,'quality':renamer, 'storynext':fix_world})

with open('fortitude/fortitude.xml') as qq:
	game_doc = etree.parse(qq)

global_lookup = {}
gameworld = StorynextElement(game_doc.getroot(), parent_id = None, global_lookup=global_lookup, local_lookup={}, class_directory=element_classes, postprocessors=postprocessors)

def prettyprint(element, indent=''):
	children = [q for q in range(len(element)) if element[q].__class__.__name__.endswith("Element")]
	lists = [q for q in range(len(element)) if not element[q].__class__.__name__.endswith("Element") and type(element[q]) == list]
	singles = [q for q in range(len(element)) if not element[q].__class__.__name__.endswith("Element") and type(element[q]) != list]
	print((element.__class__.__name__)+' '+' '.join("%s=%s"%(element._fields[q],repr(element[q])) for q in singles))
	for q in children:
		print(indent + '\t' + element._fields[q],":",end='')
		prettyprint(element[q],indent+'\t')
	for q in lists:
		print(indent + '\t' + element._fields[q],":")
		for qq in element[q]:
			print(indent+'\t\t',end='')
			prettyprint(qq,indent+'\t\t')

print("entities:", "\n\t".join(repr(q) for q in global_lookup.keys()))

prettyprint(gameworld)

print("=========================================================")

chara = character.Character(gameworld,traits=None,event_delegate=(lambda x:print(x)))
#print(chara.traits())
menu_items = list(zip(string.digits+string.ascii_lowercase,chara.eligible_storylets()))
menu_dict = dict(menu_items)
if len(menu_items) > 36:
	raise NotImplementedError("Need pagination for %d storylets"%(len(menu_items)))
for button, storylet in menu_items:
	print('%s.\t%s'%(button.upper(), storylet.title))
	# TODO: something better than this.
	preview = storylet.preview or re.split('[.!?]', storylet.body)[0]+'...'
	print("\t"+preview)
ch = getch.getch()
if ch in ('\x03','\x04','\x1b'):
	print("Bye!")
	sys.exit(0)
if ch.lower() not in menu_dict:
	print("?????")
	sys.exit(1)
chosen_storylet = menu_dict[ch.lower()]
print(storylet.title)
print(storylet.body)
menu_items = list(zip(string.digits+string.ascii_lowercase,chara.eligible_branches_for_storylet(storylet)))
menu_dict = dict(menu_items)
for button, branch in menu_items:
	print('%s.\t%s%s'%(button.upper(), '[%s]'%branch.button if branch.button else "", branch.title))
	print("\t"+branch.body)
	if branch.hint:
		print("\t(%s)"%branch.hint)
ch = getch.getch()
if ch in ('\x03','\x04','\x1b'):
	print("Bye!")
	sys.exit(0)
if ch.lower() not in menu_dict:
	print("?????")
	sys.exit(1)

	
	

#qq = open('fortitude.xml')
#	print '========'
#	print aaaa[key]
