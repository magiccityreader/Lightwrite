package undo

import (
	"github.com/magiccityreader/Lightwrite/internal/doc"
)

type EntryKind int

const (
	KindInsert EntryKind = iota
	KindDelete
	KindJoin
	KindSpan
)

type Entry struct {
	Kind EntryKind
	// insert / delete / join
	Line, Col  int
	Text       string
	Attrs      []doc.Attr
	RightText  string
	RightFmt   []doc.Attr
	RightAlign doc.Align
	// span
	Start    int
	OldDoc   []string
	OldFmt   [][]doc.Attr
	OldAlign []doc.Align
	OldLen   int
}

type Stack struct {
	entries []Entry
}

func (s *Stack) Len() int { return len(s.entries) }

func (s *Stack) trim() {
	for len(s.entries) > doc.MaxUndo {
		s.entries = s.entries[1:]
	}
}

func (s *Stack) PushSpan(d *doc.Document, start, end int) {
	if start < 0 {
		start = 0
	}
	if end < 0 || end > len(d.Lines) {
		end = len(d.Lines)
	}
	if end < start {
		end = start
	}
	oldDoc := append([]string{}, d.Lines[start:end]...)
	oldFmt := make([][]doc.Attr, end-start)
	for i := start; i < end; i++ {
		if i < len(d.Format) {
			oldFmt[i-start] = append([]doc.Attr{}, d.Format[i]...)
		}
	}
	oldAlign := append([]doc.Align{}, d.Aligns[start:min(end, len(d.Aligns))]...)
	s.entries = append(s.entries, Entry{
		Kind: KindSpan, Start: start, OldDoc: oldDoc, OldFmt: oldFmt,
		OldAlign: oldAlign, OldLen: len(d.Lines),
	})
	s.trim()
}

func (s *Stack) PushInsert(line, col int, text string) {
	if len(s.entries) > 0 && text != "" && !isSpace(text) {
		last := &s.entries[len(s.entries)-1]
		if last.Kind == KindInsert && last.Line == line &&
			last.Col+len([]rune(last.Text)) == col &&
			!endsWithSpace(last.Text) {
			last.Text += text
			return
		}
	}
	s.entries = append(s.entries, Entry{Kind: KindInsert, Line: line, Col: col, Text: text})
	s.trim()
}

func (s *Stack) PushDelete(line, col int, text string, attrs []doc.Attr) {
	s.entries = append(s.entries, Entry{
		Kind: KindDelete, Line: line, Col: col, Text: text,
		Attrs: append([]doc.Attr{}, attrs...),
	})
	s.trim()
}

func (s *Stack) PushJoin(line, col int, rightText string, rightFmt []doc.Attr, rightAlign doc.Align) {
	s.entries = append(s.entries, Entry{
		Kind: KindJoin, Line: line, Col: col, RightText: rightText,
		RightFmt: append([]doc.Attr{}, rightFmt...), RightAlign: rightAlign,
	})
	s.trim()
}

func (s *Stack) Apply(d *doc.Document) bool {
	if len(s.entries) == 0 {
		return false
	}
	e := s.entries[len(s.entries)-1]
	s.entries = s.entries[:len(s.entries)-1]
	switch e.Kind {
	case KindSpan:
		restoreSpan(d, e)
	case KindInsert:
		runes := []rune(d.Lines[e.Line])
		n := len([]rune(e.Text))
		d.Lines[e.Line] = string(append(runes[:e.Col], runes[e.Col+n:]...))
		if e.Line < len(d.Format) {
			fl := d.Format[e.Line]
			if e.Col+n <= len(fl) {
				d.Format[e.Line] = append(fl[:e.Col], fl[e.Col+n:]...)
			}
		}
	case KindDelete:
		runes := []rune(d.Lines[e.Line])
		ins := []rune(e.Text)
		d.Lines[e.Line] = string(append(append([]rune{}, runes[:e.Col]...), append(ins, runes[e.Col:]...)...))
		for len(d.Format) <= e.Line {
			d.Format = append(d.Format, []doc.Attr{})
		}
		fl := d.Format[e.Line]
		attrs := e.Attrs
		for len(attrs) < len(ins) {
			attrs = append(attrs, 0)
		}
		d.Format[e.Line] = append(fl[:e.Col], append(attrs[:len(ins)], fl[e.Col:]...)...)
	case KindJoin:
		runes := []rune(d.Lines[e.Line])
		d.Lines[e.Line] = string(runes[:e.Col])
		if e.Line < len(d.Format) {
			d.Format[e.Line] = d.Format[e.Line][:e.Col]
		}
		d.Lines = append(d.Lines[:e.Line+1], append([]string{e.RightText}, d.Lines[e.Line+1:]...)...)
		d.Format = append(d.Format[:e.Line+1], append([][]doc.Attr{append([]doc.Attr{}, e.RightFmt...)}, d.Format[e.Line+1:]...)...)
		d.Aligns = append(d.Aligns[:e.Line+1], append([]doc.Align{e.RightAlign}, d.Aligns[e.Line+1:]...)...)
	}
	d.Bump()
	return true
}

func restoreSpan(d *doc.Document, e Entry) {
	delta := len(d.Lines) - e.OldLen
	spanEnd := e.Start + len(e.OldDoc) + delta
	if spanEnd < e.Start {
		spanEnd = e.Start
	}
	if spanEnd > len(d.Lines) {
		spanEnd = len(d.Lines)
	}
	newLines := append(append([]string{}, d.Lines[:e.Start]...), e.OldDoc...)
	newLines = append(newLines, d.Lines[spanEnd:]...)
	newFmt := append(append([][]doc.Attr{}, d.Format[:min(e.Start, len(d.Format))]...), copyFmt(e.OldFmt)...)
	if spanEnd < len(d.Format) {
		newFmt = append(newFmt, d.Format[spanEnd:]...)
	}
	newAlign := append(append([]doc.Align{}, d.Aligns[:min(e.Start, len(d.Aligns))]...), e.OldAlign...)
	if spanEnd < len(d.Aligns) {
		newAlign = append(newAlign, d.Aligns[spanEnd:]...)
	}
	d.Lines, d.Format, d.Aligns = newLines, newFmt, newAlign
	for len(d.Aligns) < len(d.Lines) {
		d.Aligns = append(d.Aligns, doc.AlignLeft)
	}
	d.Aligns = d.Aligns[:len(d.Lines)]
}

func copyFmt(f [][]doc.Attr) [][]doc.Attr {
	out := make([][]doc.Attr, len(f))
	for i := range f {
		out[i] = append([]doc.Attr{}, f[i]...)
	}
	return out
}

func isSpace(s string) bool {
	for _, r := range s {
		if r != ' ' && r != '\t' && r != '\n' {
			return false
		}
	}
	return s != ""
}

func endsWithSpace(s string) bool {
	if s == "" {
		return false
	}
	r := []rune(s)
	c := r[len(r)-1]
	return c == ' ' || c == '\t' || c == '\n'
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
