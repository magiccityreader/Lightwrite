package rtf

import (
	"os"
	"strconv"
	"strings"
	"unicode"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"golang.org/x/text/encoding/charmap"
)

var rtfAlign = map[doc.Align]string{
	doc.AlignLeft:    `\ql `,
	doc.AlignCenter:  `\qc `,
	doc.AlignRight:   `\qr `,
	doc.AlignJustify: `\qj `,
}

func EscapeChar(ch rune) string {
	switch ch {
	case '\\':
		return `\\`
	case '{':
		return `\{`
	case '}':
		return `\}`
	}
	code := int(ch)
	if code < 128 {
		return string(ch)
	}
	if code > 0xFFFF {
		code -= 0x10000
		high := 0xD800 + (code >> 10)
		low := 0xDC00 + (code & 0x3FF)
		if high > 32767 {
			high -= 65536
		}
		if low > 32767 {
			low -= 65536
		}
		return `\u` + strconv.Itoa(high) + `?\u` + strconv.Itoa(low) + `?`
	}
	if code > 32767 {
		code -= 65536
	}
	return `\u` + strconv.Itoa(code) + `?`
}

func Save(d *doc.Document, path string) error {
	var parts []string
	parts = append(parts, `{\rtf1\ansi\ansicpg1252\deff0`)
	parts = append(parts, `{\fonttbl{\f0\froman Times New Roman;}}`)
	parts = append(parts, `\viewkind4\uc1\f0\fs24 `)

	curB, curI, curU := false, false, false
	closeStyles := func() {
		if curB {
			parts = append(parts, `\b0 `)
			curB = false
		}
		if curI {
			parts = append(parts, `\i0 `)
			curI = false
		}
		if curU {
			parts = append(parts, `\ul0 `)
			curU = false
		}
	}

	for i, line := range d.Lines {
		var fmtLine []doc.Attr
		if i < len(d.Format) {
			fmtLine = d.Format[i]
		} else {
			fmtLine = make([]doc.Attr, len([]rune(line)))
		}
		align := doc.GetLineAlign(d.Aligns, i)
		parts = append(parts, `\pard`+rtfAlign[align])

		if line == doc.PageBreak {
			closeStyles()
			parts = append(parts, `\page `)
			continue
		}

		headingLevel := 0
		if len(fmtLine) > 0 {
			fa := fmtLine[0]
			if fa&doc.H1 != 0 {
				headingLevel = 1
			} else if fa&doc.H2 != 0 {
				headingLevel = 2
			} else if fa&doc.H3 != 0 {
				headingLevel = 3
			}
		}
		if headingLevel > 0 {
			parts = append(parts, `\outlinelevel`+strconv.Itoa(headingLevel-1)+` `)
		}

		for j, ch := range line {
			if string(ch) == doc.PageBreak || ch == '\x0c' {
				closeStyles()
				parts = append(parts, `\page `)
				continue
			}
			attrs := doc.Attr(0)
			if j < len(fmtLine) {
				attrs = fmtLine[j]
			}
			b := attrs&doc.Bold != 0 || headingLevel > 0
			it := attrs&doc.Italic != 0 || headingLevel == 3
			u := attrs&doc.Underline != 0 || headingLevel == 1
			if b != curB {
				if b {
					parts = append(parts, `\b `)
				} else {
					parts = append(parts, `\b0 `)
				}
				curB = b
			}
			if it != curI {
				if it {
					parts = append(parts, `\i `)
				} else {
					parts = append(parts, `\i0 `)
				}
				curI = it
			}
			if u != curU {
				if u {
					parts = append(parts, `\ul `)
				} else {
					parts = append(parts, `\ul0 `)
				}
				curU = u
			}
			parts = append(parts, EscapeChar(ch))
		}
		parts = append(parts, "\\par\n")
	}
	closeStyles()
	parts = append(parts, "}")
	return os.WriteFile(path, []byte(strings.Join(parts, "")), 0o644)
}

func Parse(text string) *doc.Document {
	d := doc.New()
	d.Lines = []string{""}
	d.Format = [][]doc.Attr{{}}
	d.Aligns = nil
	style := [3]bool{}
	var styleStack [][3]bool
	curAlign := doc.AlignLeft
	curOutline := 0
	uc := 1
	var groupSkip []bool

	currentAttrs := func() doc.Attr {
		var a doc.Attr
		if style[0] {
			a |= doc.Bold
		}
		if style[1] {
			a |= doc.Italic
		}
		if style[2] {
			a |= doc.Underline
		}
		switch curOutline {
		case 1:
			a |= doc.H1
		case 2:
			a |= doc.H2
		case 3:
			a |= doc.H3
		}
		return a
	}
	addChar := func(ch rune) {
		d.Lines[len(d.Lines)-1] += string(ch)
		d.Format[len(d.Format)-1] = append(d.Format[len(d.Format)-1], currentAttrs())
	}
	addNewline := func() {
		d.Aligns = append(d.Aligns, curAlign)
		d.Lines = append(d.Lines, "")
		d.Format = append(d.Format, []doc.Attr{})
		curOutline = 0
	}

	skipWords := map[string]bool{
		"fonttbl": true, "colortbl": true, "stylesheet": true,
		"info": true, "pict": true, "header": true, "footer": true,
		"footnote": true, "filetbl": true, "listtable": true,
		"listoverridetable": true, "rsidtbl": true,
		"generator": true, "xmlnstbl": true,
	}

	i, n := 0, len(text)
	for i < n {
		c := text[i]
		switch {
		case c == '{':
			styleStack = append(styleStack, style)
			j := i + 1
			willSkip := false
			if j < n && text[j] == '\\' {
				if j+1 < n && text[j+1] == '*' {
					willSkip = true
				} else {
					k := j + 1
					word := ""
					for k < n && unicode.IsLetter(rune(text[k])) {
						word += string(text[k])
						k++
					}
					if skipWords[word] {
						willSkip = true
					}
				}
			}
			groupSkip = append(groupSkip, willSkip)
			i++
		case c == '}':
			if len(styleStack) > 0 {
				style = styleStack[len(styleStack)-1]
				styleStack = styleStack[:len(styleStack)-1]
			}
			if len(groupSkip) > 0 {
				groupSkip = groupSkip[:len(groupSkip)-1]
			}
			i++
		case anyTrue(groupSkip):
			i++
		case c == '\\':
			i++
			if i >= n {
				break
			}
			nc := text[i]
			if nc == '\\' || nc == '{' || nc == '}' {
				addChar(rune(nc))
				i++
			} else if nc == '\'' {
				if i+2 < n {
					hexStr := text[i+1 : i+3]
					if code, err := strconv.ParseInt(hexStr, 16, 0); err == nil {
						b := []byte{byte(code)}
						dec := charmap.Windows1252.NewDecoder()
						out, err := dec.Bytes(b)
						if err == nil && len(out) > 0 {
							addChar([]rune(string(out))[0])
						} else {
							addChar(rune(code))
						}
					}
					i += 3
				} else {
					i++
				}
			} else if unicode.IsLetter(rune(nc)) {
				word := ""
				for i < n && unicode.IsLetter(rune(text[i])) {
					word += string(text[i])
					i++
				}
				sign := 1
				if i < n && text[i] == '-' {
					sign = -1
					i++
				}
				num := ""
				for i < n && unicode.IsDigit(rune(text[i])) {
					num += string(text[i])
					i++
				}
				hasParam := num != ""
				var param int
				if hasParam {
					param, _ = strconv.Atoi(num)
					param *= sign
				}
				if i < n && text[i] == ' ' {
					i++
				}
				switch word {
				case "u":
					if hasParam {
						code := param
						if code < 0 {
							code += 65536
						}
						addChar(rune(code))
					}
					skipped := 0
					for skipped < uc && i < n {
						c2 := text[i]
						if c2 == '{' || c2 == '}' {
							break
						}
						if c2 == '\\' && i+1 < n && text[i+1] == '\'' {
							i += 4
							skipped++
						} else if c2 == '\\' && i+1 < n && unicode.IsLetter(rune(text[i+1])) {
							i += 2
							for i < n && unicode.IsLetter(rune(text[i])) {
								i++
							}
							if i < n && text[i] == '-' {
								i++
							}
							for i < n && unicode.IsDigit(rune(text[i])) {
								i++
							}
							if i < n && text[i] == ' ' {
								i++
							}
							skipped++
						} else {
							i++
							skipped++
						}
					}
				case "par", "line":
					addNewline()
				case "page":
					if d.Lines[len(d.Lines)-1] != "" {
						addNewline()
					}
					addChar('\x0c')
					addNewline()
				case "pard":
					curAlign = doc.AlignLeft
					curOutline = 0
				case "ql":
					curAlign = doc.AlignLeft
				case "qc":
					curAlign = doc.AlignCenter
				case "qr":
					curAlign = doc.AlignRight
				case "qj":
					curAlign = doc.AlignJustify
				case "outlinelevel":
					if hasParam && param >= 0 && param <= 2 {
						curOutline = param + 1
					}
				case "b":
					style[0] = !hasParam || param != 0
				case "i":
					style[1] = !hasParam || param != 0
				case "ul":
					style[2] = !hasParam || param != 0
				case "ulnone":
					style[2] = false
				case "uc":
					if hasParam {
						uc = param
						if uc < 0 {
							uc = 0
						}
					}
				}
			} else {
				i++
			}
		case c == '\r', c == '\n':
			i++
		default:
			addChar(rune(c))
			i++
		}
	}
	d.Aligns = append(d.Aligns, curAlign)
	if len(d.Lines) > 1 && d.Lines[len(d.Lines)-1] == "" && len(d.Format[len(d.Format)-1]) == 0 {
		d.Lines = d.Lines[:len(d.Lines)-1]
		d.Format = d.Format[:len(d.Format)-1]
		d.Aligns = d.Aligns[:len(d.Aligns)-1]
	}
	for len(d.Aligns) < len(d.Lines) {
		d.Aligns = append(d.Aligns, doc.AlignLeft)
	}
	d.Aligns = d.Aligns[:len(d.Lines)]
	return d
}

func Load(path string) (*doc.Document, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return Parse(string(b)), nil
}

func anyTrue(xs []bool) bool {
	for _, x := range xs {
		if x {
			return true
		}
	}
	return false
}
