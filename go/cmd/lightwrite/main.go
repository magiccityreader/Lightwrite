package main

import (
	"fmt"
	"os"

	"github.com/magiccityreader/Lightwrite/internal/doc"
	"github.com/magiccityreader/Lightwrite/internal/ui"
)

func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "-v", "--version", "version":
			fmt.Println("lightwrite", doc.Version)
			return
		case "-h", "--help", "help":
			fmt.Println("lightwrite [file.rtf]")
			fmt.Println("  Charm/Bubble Tea terminal word processor")
			return
		}
	}
	path := ""
	if len(os.Args) > 1 {
		path = os.Args[1]
	}
	if err := ui.Run(path); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
