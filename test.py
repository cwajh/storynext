#!/usr/bin/python3
import metatemplate
from lxml import etree
import string
import character

with open('metatemplate.xml') as qq:
	template_doc = etree.parse(qq)
element_definitions = {}
metatemplate.build_element_definitions_from_metatemplate(template_doc.getroot(),element_definitions)
print('element definitions:')
print("\n".join(sorted(["%s(%s)"%(tag, ', '.join(arg.name for arg in element_definitions[tag].arguments)) for tag in element_definitions])))

element_classes = {tag:metatemplate.element_class_for_def(element_definitions[tag],element_definitions)  for tag in element_definitions}
StorynextElement = element_classes['storynext']

def renamer(element):
	if element['name'] is None:
		element['name'] = string.capwords(element['id'])
postprocessors = {'deck':renamer,'quality':renamer}

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

chara = character.Character(gameworld,traits=None,event_delegate=(lambda x:print(x)))
print(chara.traits())
#qq = open('fortitude.xml')
#	print '========'
#	print aaaa[key]
