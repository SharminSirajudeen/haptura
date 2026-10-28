// D1's device side (plan §4e): for each "x,y" argument (top-left screen points), the app that owns the
// accessibility element under that point. One JSON object per line. Needs the Accessibility permission
// for the calling terminal; with the screen locked the hit-test fails (err -25200, measured 28 Oct).
import AppKit
import ApplicationServices

let system = AXUIElementCreateSystemWide()
for arg in CommandLine.arguments.dropFirst() {
    let p = arg.split(separator: ",").compactMap { Float($0) }
    var element: AXUIElement?
    let err = AXUIElementCopyElementAtPosition(system, p[0], p[1], &element)
    var pid: pid_t = 0
    var title: CFTypeRef?
    if let e = element {
        AXUIElementGetPid(e, &pid)
        var window: CFTypeRef?
        AXUIElementCopyAttributeValue(e, kAXWindowAttribute as CFString, &window)
        if let w = window { AXUIElementCopyAttributeValue(w as! AXUIElement, kAXTitleAttribute as CFString, &title) }
    }
    let app = NSRunningApplication(processIdentifier: pid)
    let row: [String: Any] = [
        "x": p[0], "y": p[1], "err": Int(err.rawValue), "pid": Int(pid),
        "bundle": app?.bundleIdentifier ?? "", "name": app?.localizedName ?? "", "title": title as? String ?? "",
    ]
    let data = try! JSONSerialization.data(withJSONObject: row, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}
