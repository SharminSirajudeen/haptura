// The proof's attacker (plan §4e): a borderless, always-on-top "Allow" panel drawn by a second process
// over whatever app is in front, without taking focus. Prints its frame once as "x,y,w,h" in top-left screen
// points, then exits by itself after the given number of seconds. Arguments: x y w h seconds.
import AppKit

let a = CommandLine.arguments.dropFirst().compactMap { Double($0) }
let screen = NSScreen.screens[0].frame
let rect = NSRect(x: a[0], y: screen.height - a[1] - a[3], width: a[2], height: a[3])
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let panel = NSPanel(contentRect: rect, styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
panel.level = .floating
panel.backgroundColor = .windowBackgroundColor
let button = NSButton(title: "Allow", target: nil, action: nil)
button.frame = NSRect(x: 0, y: 0, width: a[2], height: a[3])
panel.contentView?.addSubview(button)
panel.orderFrontRegardless()
print("\(Int(a[0])),\(Int(a[1])),\(Int(a[2])),\(Int(a[3]))")
fflush(stdout)
DispatchQueue.main.asyncAfter(deadline: .now() + a[4]) { exit(0) }
app.run()
