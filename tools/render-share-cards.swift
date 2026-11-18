// Optional macOS authoring tool. Generated JPEGs are committed; builds need no AppKit.
// Run from the repository root: swift tools/render-share-cards.swift
import AppKit
struct Card: Decodable { let file: String; let title: String; let subtitle: String; let thread: String; let year: String; let palette: String }
let source = URL(fileURLWithPath: FileManager.default.currentDirectoryPath).appendingPathComponent("content/share-cards.json")
let cards = try JSONDecoder().decode([Card].self, from: Data(contentsOf: source))
func color(_ hex: String) -> NSColor {
    let n = Int(hex, radix:16)!
    return NSColor(srgbRed: CGFloat((n >> 16) & 255)/255, green: CGFloat((n >> 8) & 255)/255, blue: CGFloat(n & 255)/255, alpha:1)
}
func text(_ value: String, _ rect: NSRect, _ size: CGFloat, _ ink: NSColor, serif: Bool = false) {
    let paragraph = NSMutableParagraphStyle(); paragraph.lineSpacing = 8
    let font = serif ? (NSFont(name:"Georgia",size:size) ?? .systemFont(ofSize:size)) : .systemFont(ofSize:size, weight:.regular)
    (value as NSString).draw(in:rect,withAttributes:[.font:font,.foregroundColor:ink,.paragraphStyle:paragraph])
}
for card in cards {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes:nil,pixelsWide:1200,pixelsHigh:630,bitsPerSample:8,samplesPerPixel:4,hasAlpha:true,isPlanar:false,colorSpaceName:.deviceRGB,bytesPerRow:0,bitsPerPixel:0)!
    let context = NSGraphicsContext(bitmapImageRep:bitmap)!
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.current = context
    let palette = card.palette == "teal" ? ("E4EEE8","153E3A","397367") : card.palette == "rose" ? ("F4E4DC","643D37","A55D45") : ("EBE6F0","403650","75638C")
    let paper = color(palette.0), ink = color(palette.1), accent = color(palette.2)
    paper.setFill();NSRect(x:0,y:0,width:1200,height:630).fill()
    accent.setFill();NSRect(x:0,y:0,width:16,height:630).fill()
    // Notebook rules give these cards a recognisable, restrained visual identity.
    accent.withAlphaComponent(0.24).setStroke()
    let line=NSBezierPath();line.move(to:NSPoint(x:76,y:114));line.line(to:NSPoint(x:1124,y:114));line.lineWidth=1.5;line.stroke()
    text("TIME TURNER",NSRect(x:76,y:535,width:650,height:36),25,accent)
    text(card.thread.uppercased()+" · "+card.year,NSRect(x:76,y:468,width:1000,height:34),23,accent)
    text(card.title,NSRect(x:72,y:230,width:1030,height:210),76,ink,serif:true)
    text(card.subtitle,NSRect(x:76,y:157,width:1025,height:70),27,ink)
    text("Stories from my life",NSRect(x:76,y:53,width:700,height:35),25,ink)
    text("indiantripper.in",NSRect(x:850,y:53,width:280,height:35),25,accent)
    NSGraphicsContext.restoreGraphicsState()
    let target = URL(fileURLWithPath:FileManager.default.currentDirectoryPath).appendingPathComponent("static"+card.file)
    try FileManager.default.createDirectory(at:target.deletingLastPathComponent(),withIntermediateDirectories:true)
    try bitmap.representation(using:.jpeg,properties:[.compressionFactor:0.87])!.write(to:target)
    print(target.lastPathComponent)
}
