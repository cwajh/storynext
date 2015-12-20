#!/usr/bin/python3
from collections import namedtuple
from lxml import etree
import parsedatetime
import re

re_complex_type = re.compile(r'([a-zA-Z]*)\(([a-zA-Z, ]*)\)')
re_arg_type = re.compile(r'([a-zA-Z\(\)][a-zA-Z\(\), ]*)(\[[^\]]*\])?')

ElementDefinition = namedtuple('ElementDefinition', 'tag plural arguments children id_type body_type')
ArgumentDefinition = namedtuple('ArgumentDefinition', 'name datatype default required')
ChildDefinition = namedtuple('ChildDefinition', 'tag qty')

class MetaTemplateParseError(RuntimeError):
	pass
class TemplateParseError(RuntimeError):
	pass
	
class ElementRef(namedtuple("ElementRef","type id directory")):
	def dereference(self):
		key = (self.type,self.id)
		try:
			if key in self.directory:
				return self.directory[key]
		except:
			raise
		return None
	def __repr__(self):
		return "%s%s(type=%s,id=%s)"%(("Invalid" if self.dereference() is None else "Valid"),self.__class__.__name__,repr(self.type),repr(self.id))
class LocalElementRef(ElementRef):
	pass
class GlobalElementRef(ElementRef):
	pass


def build_element_definitions_from_metatemplate(lx_elem,defs):
	tag = lx_elem.tag.lower()
	plural = lx_elem.get('mt-plural')
	id_type = lx_elem.get('mt-id')
	if id_type:
		id_type = id_type.lower()
		if id_type not in ('global','local','scoped'):
			raise MetaTemplateParseError('Element %s on line %d has unknown id type %s'%(lx_elem, lx_elem.sourceline, id_type))
	body_type = None
	if lx_elem.text is not None:
		body_type = lx_elem.text.strip()
	arguments = []
	for arg_name, arg_value in lx_elem.items():
		if arg_name.startswith('mt-'):
			continue
		type_match = re_arg_type.match(arg_value)
		if not type_match:
			raise MetaTemplateParseError('Element %s on line %d has argument %s with invalid type %s'%(lx_elem, lx_elem.sourceline, arg_name, arg_value))
		arg_type = type_match.group(1).lower()
		default_string = type_match.group(2)
		if default_string is None:
			default = None
			required = True
		else:
			required = False
			if default_string == '[None]':
				default = None
			elif arg_type.startswith('ref'):
				raise MetaTemplateParseError('Element %s on line %d has argument %s with invalid type %s (ref default)'%(lx_elem, lx_elem.sourceline, arg_name, arg_value))
			else:
				default = elem_str_to_type(default_string[1:-1], arg_type, {}, {}, None)
		arguments.append(ArgumentDefinition(arg_name.lower(), arg_type,default,required))
	children = []
	for child_elem in lx_elem:
		if not hasattr(child_elem.tag,'lower'):
			continue
		qty = child_elem.get('mt-qty')
		if qty is None:
			raise MetaTemplateParseError('Child element %s on line %d has no mt-qty.'%(child_elem,child_elem.sourceline))
		child_tag = child_elem.tag.lower()
		children.append(ChildDefinition(child_tag,qty))
		build_element_definitions_from_metatemplate(child_elem, defs)
	if children and body_type:
		raise MetaTemplateParseError('Element %s on line %d has both children %s and body type %s'%(lx_elem, lx_elem.sourceline, children, body_type))
	arguments = frozenset(arguments)
	children = frozenset(children)
	element_definition = ElementDefinition(tag, plural.lower() if plural else None, arguments, children, id_type, body_type)
	if tag in defs:
		if defs[tag] != element_definition:
			raise MetaTemplateParseError('Element definition %s on line %d conflicts with prior definition %s'%(element_definition, lx_elem.sourceline, defs[tag]))
	else:
		defs[tag] = element_definition

def inner_xml(lxml_element):
	return (lxml_element.text or "") + ''.join([etree.tostring(child).decode() for child in lxml_element])

def elem_str_to_type(s, t, global_lookup, local_lookup, parent_id):
	if t == 'int':
		return int(s)
	elif t == 'bool':
		try:
			return True if int(s) else False
		except ValueError:
			norm_s = s.lower().strip()
			if norm_s in ('y','t','yes','true','on'):
				return True
			elif norm_s in ('n','f','no','false','off'):
				return False
			else:
				raise ValueError("couldn't parse `%s` as bool", s)
	elif t == 'str':
		return s
	elif t == 'timedelta':
		value, was_parsed = parsedatetime.Calendar().parse(s)
		if not was_parsed:
			raise ValueError("couldn't parse `%s` as timedelta", s)
	elif t in ('global_id', 'local_id'):
		return s
	elif t == 'scoped_id':
		if parent_id is None:
			return s
		else:
			return "%s.%s"%(parent_id,s)
	elif re_complex_type.match(t):
		match = re_complex_type.match(t)
		reftype = match.group(1)
		reftarget = match.group(2)
		if reftype == 'ref':
			return GlobalElementRef(reftarget,s,global_lookup)
		elif reftype == 'localref':
			return LocalElementRef(reftarget,s,local_lookup)
		elif reftype == 'enum':
			options = [q.strip().lower() for q in reftarget.split(',')]
			if s.lower() in options:
				return s.lower()
			raise ValueError("couldn't parse `%s` as %s", s, t)
	else:
		raise MetaTemplateParseError('Unknown type %s', t)




def element_class_for_def(element, element_definitions):
	required_fields = []
	optional_fields = {}
	argument_types = {}
	singular_children = []
	plural_children = {}
	local_children = False
	
	for argument in element.arguments:
		if argument.required:
			required_fields.append(argument.name)
		else:
			optional_fields[argument.name] = argument.default
		argument_types[argument.name] = argument.datatype
	for child in element.children:
		if child.qty == '0+':
			optional_fields[element_definitions[child.tag].plural] = []
			plural_children[child.tag] = element_definitions[child.tag].plural
		elif child.qty == '0-1':
			optional_fields[child.tag] = None
			singular_children.append(child.tag)
		elif child.qty == '1':
			required_fields.append(child.tag)
			singular_children.append(child.tag)
		elif child.qty == '1+':
			required_fields.append(element_definitions[child.tag].plural)
			plural_children[child.tag] = element_definitions[child.tag].plural
		else:
			raise MetaTemplateParseError("Element %s has child %s with unrecognized quantity"%(element, child))
		if element_definitions[child.tag].id_type == 'local':
			local_children = True
	if element.id_type:
		required_fields += ['id']
		argument_types['id'] = element.id_type+"_id"
	if element.body_type:
		if element.children:
			raise MetaTemplateParseError('Element %s has children but also has a body'%element)
		if not required_fields and not optional_fields:
			#print 'HINT! This (%s) can be folded into a str...'%repr(element)
			#print('folding %s into a str'%repr(element))
			def bogostr_new(cls, lx_element, parent_id, global_lookup, local_lookup, class_directory, postprocessors=None):
				return str.__new__(cls, inner_xml(lx_element))
			return type(element.tag.capitalize()+"Str",(str,),{'__new__':bogostr_new})
			#
		optional_fields['body'] = ''
	all_field_names = required_fields+list(optional_fields.keys())
	storetuple = namedtuple(element.tag.capitalize()+"StorageTuple", all_field_names)
	storetuple.tag_name = element.tag

	def new_from_element(cls, lx_element, parent_id, global_lookup, local_lookup, class_directory, postprocessors={}):
		arguments = {}
		for arg_name, arg_value in lx_element.items():
			if arg_name not in all_field_names:
				raise TemplateParseError("Tag %s on line %d has unexpected argument %s"%(lx_element, lx_element.sourceline, arg_name))
			try:
				parsed_value = elem_str_to_type(arg_value, argument_types[arg_name], global_lookup, local_lookup, parent_id)
				arguments[arg_name] = parsed_value
			except ValueError:
				raise TemplateParseError("Argument %s=%s of tag %s on line %d couldn't be parsed as a %s",(arg_name,arg_value,lx_element, lx_element.sourceline, argument_types[arg_name]))
			except KeyError:
				raise
		id_for_children = parent_id
		if 'id' in arguments:
			id_for_children = arguments['id']
		# Make a local copy so that this element's local children won't be shared by any of our ancestors or cousins.
		if local_children:
			children_local_lookup = dict(local_lookup)
		else:
			children_local_lookup = local_lookup
		if element.body_type:
			arguments['body'] = inner_xml(lx_element)
		else:
			for child_elem in lx_element:
				# Best way I know to detect/skip comments right now.
				if not hasattr(child_elem.tag,'lower'):
					continue
				child_tag = child_elem.tag.lower()
				if not child_tag in class_directory:
					raise TemplateParseError('Tag %s on line %d is an unknown type'%(child_elem, child_elem.sourceline))
				child = class_directory[child_tag](child_elem, id_for_children, global_lookup, children_local_lookup, class_directory, postprocessors)
				if child_tag in plural_children:
					arg_name = plural_children[child_tag]
					if arg_name in arguments:
						arguments[arg_name].append(child)
					else:
						arguments[arg_name] = [child]
				elif child_tag in singular_children:
					arguments[child_tag] = child
				else:
					raise TemplateParseError("Tag %s on line %d is an unexpected child of tag %s on line %d (expected %s)"%(child_elem, child_elem.sourceline, lx_element, lx_element.sourceline, element.children))
		missing_required_args = [arg_name for arg_name in required_fields if arg_name not in arguments]
		if missing_required_args:
			raise TemplateParseError("Tag %s on line %d is missing arguments: %s"%(lx_element, lx_element.sourceline, missing_required_args))
		for arg_name in optional_fields:
			if arg_name not in arguments:
				arguments[arg_name] = optional_fields[arg_name]
		if element.tag in postprocessors:
			postprocessors[element.tag](arguments)
			
		new_element = storetuple.__new__(cls, **arguments)
		if 'id' in arguments:
			lookup_key = (element.tag, arguments['id'])
			if element.id_type == 'local':
				local_lookup[lookup_key] = new_element
			else:
				if lookup_key in global_lookup:
					raise TemplateParseError("Tag %s on line %d has an ID %s that's already in use by %s"%(lx_element,lx_element.sourceline,lookup_key,global_lookup[lookup_key]))
				global_lookup[lookup_key] = new_element
		return new_element
	return type(element.tag.capitalize()+"Element", (storetuple,), {"__new__":new_from_element})
