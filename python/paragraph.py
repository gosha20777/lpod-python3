# -*- coding: UTF-8 -*-
#
# Copyright (c) 2009 Ars Aperta, Itaapy, Pierlis, Talend.
#
# Authors: David Versmisse <david.versmisse@itaapy.com>
#          Hervé Cauwelier <herve@itaapy.com>
#          Romain Gauthier <romain@itaapy.com>
#
# This file is part of Lpod (see: http://lpod-project.org).
# Lpod is free software; you can redistribute it and/or modify it under
# the terms of either:
#
# a) the GNU General Public License as published by the Free Software
#    Foundation, either version 3 of the License, or (at your option)
#    any later version.
#    Lpod is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#    You should have received a copy of the GNU General Public License
#    along with Lpod.  If not, see <http://www.gnu.org/licenses/>.
#
# b) the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
#

# Import from the Standard Library
from re import compile, escape

# Import from lpod
from element import register_element_class, odf_element, odf_create_element
from element import FIRST_CHILD, odf_text
from note import odf_create_note, odf_create_annotation
from span import odf_create_span
from style import odf_style


def _get_formated_text(element, context, with_text=True):
    result = []
    if with_text:
        objects = element.xpath('*|text()')
    else:
        objects = element.get_children()
    for obj in objects:
        if type(obj) is odf_text:
            result.append(obj)
        else:
            tag = obj.get_tagname()
            # Good tags with text
            if tag in ('text:span', 'text:a', 'text:p'):
                result.append(_get_formated_text(obj, context,
                                                 with_text=True))
            # Footnote or endnote
            elif tag == 'text:note':
                note_class = obj.get_note_class()
                container = {'footnote': context['footnotes'],
                             'endnote': context['endnotes']}[note_class]
                citation = obj.get_note_citation()
                if not citation:
                    # Would only happen with hand-made documents
                    citation = len(container)
                body = obj.get_note_body()
                container.append((citation, body))
                marker = {'footnote': u"[%s]",
                          'endnote': u"(%s)"}[note_class]
                result.append(marker % citation)
            # Annotations
            elif tag == 'office:annotation':
                context['annotations'].append(obj.get_annotation_body())
                result.append('[*]')
            # Tabulation
            elif tag == 'text:tab':
                result.append(u'\t')
            # Line break
            elif tag == 'text:line-break':
                result.append(u"\n")
            else:
                result.append(obj.get_formated_text(context))
    return u''.join(result)



def odf_create_paragraph(text=None, style=None):
    """Create a paragraph element of the given style containing the optional
    given text.

    Arguments:

        style -- unicode

        text -- unicode

    Return: odf_element
    """
    element = odf_create_element('<text:p/>')
    if text:
        element.set_text(text)
    if style:
        element.set_attribute('text:style-name', style)
    return element



class odf_paragraph(odf_element):
    """Specialised element for paragraphs.
    """
    def get_formated_text(self, context):
        result = [_get_formated_text(self, context, with_text=True)]
        result.append(u'\n')
        return u''.join(result)


    def insert_note(self, note_element=None, after=None,
                    note_class='footnote', note_id=None, citation=None,
                    body=None, *args, **kw):
        if note_element is None:
            note_element = odf_create_note(note_class=note_class,
                                           note_id=note_id,
                                           citation=citation, body=body)
        else:
            # XXX clone or modify the argument?
            if note_class:
                note_element.set_note_class(note_class)
            if note_id:
                note_element.set_note_id(note_id, *args, **kw)
            if citation:
                note_element.set_note_citation(citation)
            if body:
                note_element.set_note_body(body)
        note_element.check_validity()
        if type(after) is unicode:
            self._insert_after(note_element, after)
        elif isinstance(after, odf_element):
            after.insert_element(note_element, FIRST_CHILD)
        else:
            self.insert_element(note_element, FIRST_CHILD)


    def insert_annotation(self, annotation_element=None, after=None,
                          body=None, creator=None, date=None):
        if annotation_element is None:
            annotation_element = odf_create_annotation(body,
                                                       creator=creator,
                                                       date=date)
        else:
            # XXX clone or modify the argument?
            if body:
                annotation_element.set_annotation_body(body)
            if creator:
                annotation_element.set_dc_creator(creator)
            if date:
                annotation_element.set_dc_date(date)
        annotation_element.check_validity()
        if type(after) is unicode:
            self._insert_after(annotation_element, after)
        elif isinstance(after, odf_element):
            after.insert_element(annotation_element, FIRST_CHILD)
        else:
            self.insert_element(annotation_element, FIRST_CHILD)


    def insert_variable(self, variable_element,  after):
        self._insert_after(variable_element, after)


    def set_span(self, style, regex=None, offset=None, length=0):
        """Apply the given style to text content matching the regex OR the
        positional arguments offset and length.

        Arguments:

            style -- style element or name

            regex -- unicode regular expression

            offset -- int

            length -- int
        """
        if isinstance(style, odf_style):
            style = style.get_style_name()
        if offset:
            # XXX quickly hacking the offset
            text = self.get_text()
            if length:
                regex = text[offset:offset + length]
            else:
                regex = text[offset:]
            regex = escape(regex)
        if regex:
            pattern = compile(unicode(regex))
            for text in self.xpath('descendant::text()'):
                # Static information about the text node
                container = text.get_parent()
                wrapper = container.get_parent()
                is_text = text.is_text()
                is_tail = text.is_tail()
                # Group positions are calculated and static, so apply in
                # reverse order to preserve positions
                for group in reversed(list(pattern.finditer(text))):
                    start, end = group.span()
                    # Do not use the text node as it changes at each loop
                    if is_text:
                        text = container.get_text()
                    else:
                        text = container.get_tail()
                    before = text[:start]
                    match = text[start:end]
                    after = text[end:]
                    span = odf_create_span(match, style=style)
                    span.set_tail(after)
                    if is_text:
                        container.set_text(before)
                        # Insert as first child
                        container.insert_element(span, position=0)
                    else:
                        container.set_tail(before)
                        # Insert as next sibling
                        index = wrapper.index(container)
                        wrapper.insert_element(span, position=index + 1)


    def set_link(self, url, regex=None, offset=None, length=0):
        """Make a link from text content matching the regex OR the positional
        arguments.
        """
        raise NotImplementedError



register_element_class('text:p', odf_paragraph)
