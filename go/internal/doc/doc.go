package doc

import (
	"strings"
	"unicode/utf8"
)

const (
	Bold        Attr = 1
	Italic      Attr = 2
	Underline   Attr = 4
	H1          Attr = 8
	H2          Attr = 16
	H3          Attr = 32
	HeadingMask      = H1 | H2 | H3

	AlignLeft Align = iota
	AlignCenter
	AlignRight
	AlignJustify

	PageBreak = "\x0c"
	Version   = "2.0.0"
	MaxUndo   = 300
	TextWidth = 80
)

type Attr int
type Align int

type Document struct {
	Lines   []string
	Format  [][]Attr
	Aligns  []Align
	Version int
}

func New() *Document {
	return &Document{
		Lines:  []string{""},
		Format: [][]Attr{{}},
		Aligns: []Align{AlignLeft},
	}
}

func (d *Document) Bump() { d.Version++ }

func (d *Document) ensureAligns() {
	for len(d.Aligns) < len(d.Lines) {
		d.Aligns = append(d.Aligns, AlignLeft)
	}
	d.Aligns = d.Aligns[:len(d.Lines)]
}

func (d *Document) String() string {
	return strings.Join(d.Lines, "\n")
}

func (d *Document) WordCount() int {
	t := strings.ReplaceAll(d.String(), PageBreak, " ")
	return len(strings.Fields(t))
}

func runeLen(s string) int { return utf8.RuneCountInString(s) }

func GetLineAlign(aligns []Align, i int) Align {
	if i < 0 || i >= len(aligns) {
		return AlignLeft
	}
	return aligns[i]
}

func GetLineHeadingLevel(format [][]Attr, line int) int {
	if line < 0 || line >= len(format) || len(format[line]) == 0 {
		return 0
	}
	a := format[line][0]
	switch {
	case a&H1 != 0:
		return 1
	case a&H2 != 0:
		return 2
	case a&H3 != 0:
		return 3
	}
	return 0
}

func SetLineHeading(format [][]Attr, line, level int) [][]Attr {
	if line < 0 || line >= len(format) || len(format[line]) == 0 {
		return format
	}
	var bit Attr
	switch level {
	case 1:
		bit = H1
	case 2:
		bit = H2
	case 3:
		bit = H3
	}
	fl := format[line]
	for i := range fl {
		fl[i] = (fl[i] &^ HeadingMask) | bit
	}
	return format
}

type Heading struct {
	Line  int
	Level int
	Title string
}

func CollectHeadings(d *Document) []Heading {
	var out []Heading
	for i := range d.Lines {
		if lvl := GetLineHeadingLevel(d.Format, i); lvl > 0 {
			out = append(out, Heading{Line: i, Level: lvl, Title: d.Lines[i]})
		}
	}
	return out
}

func PositionToAbsolute(lines []string, line, col int) int {
	abs := 0
	for i := 0; i < line && i < len(lines); i++ {
		abs += runeLen(lines[i]) + 1
	}
	if line < len(lines) {
		n := runeLen(lines[line])
		if col > n {
			col = n
		}
		abs += col
	}
	return abs
}

func AbsoluteToPosition(text string, absolute int) (line, col int) {
	runes := []rune(text)
	if absolute < 0 {
		absolute = 0
	}
	if absolute > len(runes) {
		absolute = len(runes)
	}
	before := string(runes[:absolute])
	line = strings.Count(before, "\n")
	if i := strings.LastIndex(before, "\n"); i >= 0 {
		col = runeLen(before[i+1:])
	} else {
		col = runeLen(before)
	}
	return line, col
}

type Cell struct {
	Ch    rune
	Attrs Attr
}

func DocumentToCells(d *Document) []Cell {
	var cells []Cell
	for i, line := range d.Lines {
		var fl []Attr
		if i < len(d.Format) {
			fl = d.Format[i]
		}
		for j, r := range line {
			a := Attr(0)
			if j < len(fl) {
				a = fl[j]
			}
			cells = append(cells, Cell{Ch: r, Attrs: a})
		}
		if i < len(d.Lines)-1 {
			cells = append(cells, Cell{Ch: '\n'})
		}
	}
	return cells
}

func CellsToDocument(cells []Cell) (lines []string, format [][]Attr) {
	lines = []string{""}
	format = [][]Attr{{}}
	for _, c := range cells {
		if c.Ch == '\n' {
			lines = append(lines, "")
			format = append(format, []Attr{})
			continue
		}
		lines[len(lines)-1] += string(c.Ch)
		format[len(format)-1] = append(format[len(format)-1], c.Attrs)
	}
	return lines, format
}

func TextToCells(text string, attrs Attr) []Cell {
	var cells []Cell
	for _, r := range text {
		if r == '\n' {
			cells = append(cells, Cell{Ch: '\n'})
		} else {
			cells = append(cells, Cell{Ch: r, Attrs: attrs})
		}
	}
	return cells
}

func CellsToText(cells []Cell) string {
	var b strings.Builder
	for _, c := range cells {
		b.WriteRune(c.Ch)
	}
	return b.String()
}

func InsertRunes(d *Document, line, col int, s string, attrs Attr) (int, int) {
	if line < 0 || line >= len(d.Lines) {
		return line, col
	}
	runes := []rune(s)
	ln := []rune(d.Lines[line])
	if col > len(ln) {
		col = len(ln)
	}
	d.Lines[line] = string(append(append([]rune{}, ln[:col]...), append(runes, ln[col:]...)...))
	for len(d.Format) <= line {
		d.Format = append(d.Format, []Attr{})
	}
	fl := d.Format[line]
	for len(fl) < len(ln) {
		fl = append(fl, 0)
	}
	fl = fl[:len(ln)]
	ins := make([]Attr, len(runes))
	for i := range ins {
		ins[i] = attrs
	}
	d.Format[line] = append(fl[:col], append(ins, fl[col:]...)...)
	d.Bump()
	return line, col + len(runes)
}

func DeleteBefore(d *Document, line, col int) (int, int) {
	d.ensureAligns()
	if col > 0 {
		runes := []rune(d.Lines[line])
		d.Lines[line] = string(append(runes[:col-1], runes[col:]...))
		if line < len(d.Format) && col-1 < len(d.Format[line]) {
			fl := d.Format[line]
			d.Format[line] = append(fl[:col-1], fl[col:]...)
		}
		col--
	} else if line > 0 {
		prevLen := runeLen(d.Lines[line-1])
		d.Lines[line-1] += d.Lines[line]
		if line < len(d.Format) {
			d.Format[line-1] = append(d.Format[line-1], d.Format[line]...)
			d.Format = append(d.Format[:line], d.Format[line+1:]...)
		}
		d.Lines = append(d.Lines[:line], d.Lines[line+1:]...)
		if line < len(d.Aligns) {
			d.Aligns = append(d.Aligns[:line], d.Aligns[line+1:]...)
		}
		line--
		col = prevLen
	}
	d.Bump()
	return line, col
}

func DeleteAt(d *Document, line, col int) (int, int) {
	d.ensureAligns()
	runes := []rune(d.Lines[line])
	if col < len(runes) {
		d.Lines[line] = string(append(runes[:col], runes[col+1:]...))
		if line < len(d.Format) && col < len(d.Format[line]) {
			fl := d.Format[line]
			d.Format[line] = append(fl[:col], fl[col+1:]...)
		}
	} else if line < len(d.Lines)-1 {
		d.Lines[line] += d.Lines[line+1]
		if line+1 < len(d.Format) {
			d.Format[line] = append(d.Format[line], d.Format[line+1]...)
			d.Format = append(d.Format[:line+1], d.Format[line+2:]...)
		}
		d.Lines = append(d.Lines[:line+1], d.Lines[line+2:]...)
		if line+1 < len(d.Aligns) {
			d.Aligns = append(d.Aligns[:line+1], d.Aligns[line+2:]...)
		}
	}
	d.Bump()
	return line, col
}

func Enter(d *Document, line, col int) (int, int) {
	d.ensureAligns()
	runes := []rune(d.Lines[line])
	if col > len(runes) {
		col = len(runes)
	}
	left, right := string(runes[:col]), string(runes[col:])
	var leftFmt, rightFmt []Attr
	if line < len(d.Format) {
		fl := d.Format[line]
		for len(fl) < len(runes) {
			fl = append(fl, 0)
		}
		leftFmt = append([]Attr{}, fl[:col]...)
		rightFmt = append([]Attr{}, fl[col:]...)
		d.Format[line] = leftFmt
	}
	d.Lines[line] = left
	d.Lines = append(d.Lines[:line+1], append([]string{right}, d.Lines[line+1:]...)...)
	d.Format = append(d.Format[:line+1], append([][]Attr{rightFmt}, d.Format[line+1:]...)...)
	al := GetLineAlign(d.Aligns, line)
	d.Aligns = append(d.Aligns[:line+1], append([]Align{al}, d.Aligns[line+1:]...)...)
	d.Bump()
	return line + 1, 0
}

func InsertPageBreak(d *Document, line, col int) (int, int) {
	d.ensureAligns()
	runes := []rune(d.Lines[line])
	if col > len(runes) {
		col = len(runes)
	}
	left, right := string(runes[:col]), string(runes[col:])
	var leftFmt, rightFmt []Attr
	if line < len(d.Format) {
		fl := d.Format[line]
		for len(fl) < len(runes) {
			fl = append(fl, 0)
		}
		leftFmt = append([]Attr{}, fl[:col]...)
		rightFmt = append([]Attr{}, fl[col:]...)
		d.Format[line] = leftFmt
	}
	d.Lines[line] = left
	d.Lines = append(d.Lines[:line+1], append([]string{PageBreak, right}, d.Lines[line+1:]...)...)
	d.Format = append(d.Format[:line+1], append([][]Attr{{0}, rightFmt}, d.Format[line+1:]...)...)
	al := GetLineAlign(d.Aligns, line)
	d.Aligns = append(d.Aligns[:line+1], append([]Align{al, al}, d.Aligns[line+1:]...)...)
	d.Bump()
	return line + 2, 0
}

func ApplyAttrToSelection(d *Document, start, end [2]int, attr Attr) {
	a := PositionToAbsolute(d.Lines, start[0], start[1])
	b := PositionToAbsolute(d.Lines, end[0], end[1])
	if a > b {
		a, b = b, a
	}
	if a == b {
		return
	}
	text := d.String()
	lineA, colA := AbsoluteToPosition(text, a)
	lineB, colB := AbsoluteToPosition(text, b)
	allSet, anyChar := true, false
	for li := lineA; li <= lineB; li++ {
		if li >= len(d.Format) {
			continue
		}
		c0, c1 := 0, runeLen(d.Lines[li])
		if li == lineA {
			c0 = colA
		}
		if li == lineB {
			c1 = colB
		}
		fl := d.Format[li]
		for ci := c0; ci < c1 && ci < len(fl); ci++ {
			anyChar = true
			if fl[ci]&attr == 0 {
				allSet = false
				break
			}
		}
		if anyChar && !allSet {
			break
		}
	}
	if !anyChar {
		return
	}
	for li := lineA; li <= lineB; li++ {
		if li >= len(d.Format) {
			continue
		}
		c0, c1 := 0, runeLen(d.Lines[li])
		if li == lineA {
			c0 = colA
		}
		if li == lineB {
			c1 = colB
		}
		fl := d.Format[li]
		for ci := c0; ci < c1 && ci < len(fl); ci++ {
			if allSet {
				fl[ci] &^= attr
			} else {
				fl[ci] |= attr
			}
		}
	}
	d.Bump()
}

func ApplyAlignment(d *Document, cursorLine int, start, end *[2]int, align Align) {
	d.ensureAligns()
	from, to := cursorLine, cursorLine
	if start != nil && end != nil {
		a := PositionToAbsolute(d.Lines, start[0], start[1])
		b := PositionToAbsolute(d.Lines, end[0], end[1])
		if a > b {
			a, b = b, a
		}
		text := d.String()
		from, _ = AbsoluteToPosition(text, a)
		to, _ = AbsoluteToPosition(text, b)
		if a != b {
			before := string([]rune(text)[:b])
			if strings.HasSuffix(before, "\n") && to > from {
				to--
			}
		}
	}
	for i := from; i <= to && i < len(d.Aligns); i++ {
		d.Aligns[i] = align
	}
	d.Bump()
}

func FindAll(d *Document, term string) [][2]int {
	if term == "" {
		return nil
	}
	text := d.String()
	lowerText := strings.ToLower(text)
	lowerTerm := strings.ToLower(term)
	var positions [][2]int
	start, step := 0, len([]rune(lowerTerm))
	if step < 1 {
		step = 1
	}
	lt := []rune(lowerText)
	termR := []rune(lowerTerm)
	for start <= len(lt)-len(termR) {
		if string(lt[start:start+len(termR)]) == string(termR) {
			l, c := AbsoluteToPosition(text, start)
			positions = append(positions, [2]int{l, c})
			start += step
		} else {
			start++
		}
	}
	return positions
}

func ReplaceAll(d *Document, term, replacement string) int {
	if term == "" {
		return 0
	}
	replacement = strings.ReplaceAll(replacement, "\\n", "\n")
	cells := DocumentToCells(d)
	termR := []rune(strings.ToLower(term))
	tlen := len(termR)
	count := 0
	var result []Cell
	i := 0
	for i < len(cells) {
		match := i+tlen <= len(cells)
		if match {
			for k := 0; k < tlen; k++ {
				if unicodeLower(cells[i+k].Ch) != termR[k] {
					match = false
					break
				}
			}
		}
		if match {
			attrs := cells[i].Attrs
			for _, ch := range replacement {
				if ch == '\n' {
					result = append(result, Cell{Ch: '\n'})
				} else {
					result = append(result, Cell{Ch: ch, Attrs: attrs})
				}
			}
			i += tlen
			count++
		} else {
			result = append(result, cells[i])
			i++
		}
	}
	d.Lines, d.Format = CellsToDocument(result)
	d.ensureAligns()
	d.Bump()
	return count
}

func unicodeLower(r rune) rune {
	return []rune(strings.ToLower(string(r)))[0]
}

func MoveLeft(d *Document, line, col int) (int, int) {
	if col > 0 {
		return line, col - 1
	}
	if line > 0 {
		line--
		return line, runeLen(d.Lines[line])
	}
	return line, col
}

func MoveRight(d *Document, line, col int) (int, int) {
	n := runeLen(d.Lines[line])
	if col < n {
		return line, col + 1
	}
	if line < len(d.Lines)-1 {
		return line + 1, 0
	}
	return line, col
}

func DeleteSelection(d *Document, start, end [2]int) (line, col int) {
	a := PositionToAbsolute(d.Lines, start[0], start[1])
	b := PositionToAbsolute(d.Lines, end[0], end[1])
	if a > b {
		a, b = b, a
	}
	if a == b {
		return start[0], start[1]
	}
	cells := DocumentToCells(d)
	if a > len(cells) {
		a = len(cells)
	}
	if b > len(cells) {
		b = len(cells)
	}
	startLine := start[0]
	if end[0] < startLine {
		startLine = end[0]
	}
	oldLen := len(d.Lines)
	newCells := append(append([]Cell{}, cells[:a]...), cells[b:]...)
	d.Lines, d.Format = CellsToDocument(newCells)
	nRemoved := oldLen - len(d.Lines)
	before := CellsToText(newCells[:a])
	line = strings.Count(before, "\n")
	if i := strings.LastIndex(before, "\n"); i >= 0 {
		col = runeLen(before[i+1:])
	} else {
		col = runeLen(before)
	}
	keep := GetLineAlign(d.Aligns, startLine)
	head := append([]Align{}, d.Aligns[:min(startLine, len(d.Aligns))]...)
	tailStart := startLine + nRemoved + 1
	var tail []Align
	if tailStart < len(d.Aligns) {
		tail = d.Aligns[tailStart:]
	}
	d.Aligns = append(append(head, keep), tail...)
	d.ensureAligns()
	d.Bump()
	return line, col
}

func SelectedCells(d *Document, start, end [2]int) []Cell {
	a := PositionToAbsolute(d.Lines, start[0], start[1])
	b := PositionToAbsolute(d.Lines, end[0], end[1])
	if a > b {
		a, b = b, a
	}
	cells := DocumentToCells(d)
	if a > len(cells) {
		a = len(cells)
	}
	if b > len(cells) {
		b = len(cells)
	}
	return append([]Cell{}, cells[a:b]...)
}

func InsertCells(d *Document, line, col int, cells []Cell) (int, int) {
	abs := PositionToAbsolute(d.Lines, line, col)
	all := DocumentToCells(d)
	oldLen := len(d.Lines)
	all = append(all[:abs], append(cells, all[abs:]...)...)
	d.Lines, d.Format = CellsToDocument(all)
	nAdded := len(d.Lines) - oldLen
	d.ensureAligns()
	for i := 0; i < nAdded; i++ {
		at := line + 1
		if at > len(d.Aligns) {
			at = len(d.Aligns)
		}
		d.Aligns = append(d.Aligns[:at], append([]Align{AlignLeft}, d.Aligns[at:]...)...)
	}
	d.ensureAligns()
	after := CellsToText(all[:abs+len(cells)])
	nl := strings.Count(after, "\n")
	var ncol int
	if i := strings.LastIndex(after, "\n"); i >= 0 {
		ncol = runeLen(after[i+1:])
	} else {
		ncol = runeLen(after)
	}
	d.Bump()
	return nl, ncol
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
