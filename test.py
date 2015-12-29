#!/usr/bin/python3
import metatemplate
from lxml import etree
import string
import character
import itertools
import re
import getch
import sys
import tempfile
import subprocess

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


def choose_from_options(options, print_option_for_menu_item):
	menu_items = list(zip(string.digits+string.ascii_lowercase,options))
	menu_dict = dict(menu_items)
	if len(menu_items) > 36:
		raise NotImplementedError("Need pagination for %d storylets"%(len(menu_items)))
	for button, choice in menu_items:
		print_option_for_menu_item(button, choice)
	ch = getch.getch()
	if ch in ('\x03','\x04','\x1b'):
		print("Bye!")
		sys.exit(0)
	if ch.lower() not in menu_dict:
		print("?????")
		sys.exit(1)
	return menu_dict[ch.lower()]


def choose_storylet(storylets):
	def print_option(button, storylet):
		print('%s.\t%s'%(button.upper(), storylet.title))
		# TODO: better way to autogen preview text
		preview = storylet.preview or re.split('[.!?]', storylet.body)[0]+'...'
		print("\t"+preview)
	return choose_from_options(storylets, print_option)
def choose_branch(branches):
	def print_option(button, branch):
		print('%s.\t%s%s'%(button.upper(), '[%s]'%branch.button if branch.button else "", branch.title))
		print("\t"+branch.body)
		if branch.hint:
			print("\t(%s)"%branch.hint)
	return choose_from_options(branches, print_option)


chara = character.Character(gameworld,traits=None,event_delegate=(lambda x:print(x)))

print("=========================================================")
storylets = chara.eligible_storylets()
storylet = choose_storylet(storylets)
print("---------------------------------------------------------")
print(storylet.title)
print(storylet.body)
branches = chara.eligible_branches_for_storylet(storylet)
chosen_branch = choose_branch(branches)
print("---------------------------------------------------------")
result = chara.result_of_taking_branch(chosen_branch)
print(result.title)
with tempfile.NamedTemporaryFile() as body:
	body.write(result.body.encode())
	body.flush()
	subprocess.call(['links','-dump',body.name])

	
	

#qq = open('fortitude.xml')
#	print '========'
#	print aaaa[key]
