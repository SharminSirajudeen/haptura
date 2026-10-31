# Can an app on the phone itself see which app owns a window? (31 Oct 2026, $0)

The gate in `phone/` runs on a computer and reads each window's owner from Android's input dispatcher over adb, keyed by
the uid Android assigns to each app. Reading that list needs the DUMP permission, which on this emulator is
`prot=signature|privileged|development` (`adb shell dumpsys package android`): installing an app does not grant it. An app
on the phone can run an accessibility service instead. Its window list (`AccessibilityWindowInfo`) carries no package and
no uid (`android/view/accessibility/AccessibilityWindowInfo.java`; every `.java` file named here is from the SDK's
android-36 sources): the only app name it offers is the package name on the window's root node, and that node is built
inside the app that drew the window (`View.java:11470`, `info.setPackageName(mContext.getPackageName())`). Two questions,
tested on the emulator (Small_Phone, API 36, build `BE2A.250530.026.D1`) with the probe app below, which logs every window
`getWindows()` returns.

**1. Does the service see an attacker's dialog, and name its app?** GhostEI case 26's "System Update Required" dialog,
fired over Clock:
```
# GhostEI case 26's dialog over Clock; the probe service's view (31 Oct 2026, emulator-5554, API 36)
10-31 15:57:14.392 17523 17523 I A11YPROBE: windows:
10-31 15:57:14.392 17523 17523 I A11YPROBE:   type=3 layer=1 focused=false bounds=[0,0][720,48] title=null rootPackage=com.android.systemui
10-31 15:57:14.392 17523 17523 I A11YPROBE:   type=3 layer=0 focused=true bounds=[0,0][720,1280] title=null rootPackage=com.example.myapplication
```
Yes: the dialog is the focused full-screen window and its root node names `com.example.myapplication`, GhostEI's helper.
The input dispatcher, which the gate reads, has the same window owned by uid 10217, and
`adb shell cmd package list packages -U` maps that uid to the same app (fired again for this line):
```
name=74dd0c3 Sys2038:com.example.myapplication/com.example.myapplication.PopupActivity, ... frame=[0,0][720,1280], ... ownerUid=10217
package:com.example.myapplication uid:10217
```
Type 2038 is `TYPE_APPLICATION_OVERLAY` (`WindowManager.java:2350`, `:2640`). Clock's window is not in the service's list
while the dialog covers it: `getWindows()` returns only the windows a user can interact with
(`AccessibilityService.java:1051`). This run's log line predates the `rootDesc` field in the probe below.

**2. Can an app make its window claim another app's name?** The probe's `ClaimActivity`, a dialog over Clock, sets
`com.google.android.deskclock` as the package on its root view and its button, and writes the name it reads back into
the root's description:
```
10-31 15:58:28.896 17789 17789 I A11YPROBE: windows:
10-31 15:58:28.896 17789 17789 I A11YPROBE:   type=3 layer=1 focused=false bounds=[0,0][720,48] title=null rootPackage=com.android.systemui rootDesc=null
10-31 15:58:28.896 17789 17789 I A11YPROBE:   type=1 layer=0 focused=true bounds=[40,515][680,765] title=Claim rootPackage=probe.a11y rootDesc=claims com.google.android.deskclock
```
No: inside the app the name was set (the description reads "claims com.google.android.deskclock"), but the service
received `probe.a11y`, the app's own. In an earlier run of the same test, before the description was added, uiautomator
(which reads the same nodes) and the input dispatcher both named the probe for the dialog's Cancel button:
```
text="Cancel" resource-id="" class="android.widget.Button" package="probe.a11y"
gate owner at Cancel (360, 685) = probe.a11y -> block
```
(the second line is the gate's own owner check, from the dispatcher's uid, not from the node; no tap was sent).

**Why the name was replaced.** Two steps, read from the SDK sources and from this emulator's `services.jar`
(`/system/framework/services.jar`, disassembled with build-tools 36.0.0 `dexdump`):
- When a window registers with accessibility (`AccessibilityWindowManager.addAccessibilityInteractionConnection`), the
  system keeps the package it reports only if that package belongs to the window's uid, is a widget the uid hosts, or the
  caller holds `ACT_AS_PACKAGE_FOR_ACCESSIBILITY` (`prot=signature`); otherwise it records the uid's first package
  (`AccessibilitySecurityPolicy.resolveValidReportedPackageLocked`). Windows of app id 1000 keep whatever they report.
- Each time a service reads nodes, the system sends a list of valid names with them: the package the window registered
  under, plus the packages of any widgets its uid hosts; for app id 1000, an empty list
  (`AccessibilitySecurityPolicy.computeValidReportedPackages`). The framework in the service's own process replaces any
  node name not on the list with the list's first entry, and leaves names alone when the list is empty
  (`AccessibilityInteractionClient.java:671`, `:1451-1463`).

**What this shows:** an accessibility service on the phone can name the app that owns the focused window from a name the
system checked when that window registered: for windows of ordinary app uids, an app cannot claim another app's package,
except, from the code above, the package of a widget it hosts (not tested). Windows of app id 1000 carry names nobody
checks; on this emulator that uid holds both `android` and `com.android.settings` (`cmd package list packages -U`).
No on-phone version of the gate is built.

**Not checked:** a physical phone; whether an app can get a widget of another app bound, and so claim that app's name;
the owner at a tap point when the list holds more than one app's window (an overlay that does not take focus, or the
keyboard, leaves the covered app's window in the list, and the owner under a point then needs each window's layer and
`getRegionInScreen()`, which the probe does not use); a window whose `getRoot()` is null, which an on-phone gate would
have to refuse; whether a one-time `pm grant` of DUMP from a computer, which the `development` flag is for, would let an
app read the dispatcher's list itself; whether Google Play accepts an accessibility service used this way.

**Afterwards:** probe uninstalled, accessibility off, and `uiautomator dump` still works:
```
$ adb -s emulator-5554 shell settings get secure enabled_accessibility_services
null
$ adb -s emulator-5554 shell settings get secure accessibility_enabled
0
$ adb -s emulator-5554 shell pm list packages | grep -c probe
0
$ adb -s emulator-5554 shell uiautomator dump /sdcard/u.xml
UI hierchary dumped to: /sdcard/u.xml
```

**Rerun:** build the probe below with the SDK's build tools (aapt2, javac against `platforms/android-36/android.jar`, d8,
zipalign, apksigner), install it on the emulator, then, with every command on `adb -s emulator-5554`:
`shell settings put secure enabled_accessibility_services probe.a11y/.ProbeService`,
`shell settings put secure accessibility_enabled 1`, and read `logcat -s A11YPROBE:I`. Test 2, over Clock:
`shell am start -n probe.a11y/.ClaimActivity --es as com.google.android.deskclock`. Afterwards:
`shell settings delete secure enabled_accessibility_services`, `shell settings put secure accessibility_enabled 0`,
`uninstall probe.a11y`.

`AndroidManifest.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="probe.a11y">
  <uses-sdk android:minSdkVersion="30" android:targetSdkVersion="36"/>
  <application android:label="Probe">
    <service android:name=".ProbeService" android:exported="false"
        android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
      <intent-filter><action android:name="android.accessibilityservice.AccessibilityService"/></intent-filter>
      <meta-data android:name="android.accessibilityservice" android:resource="@xml/probe"/>
    </service>
    <activity android:name=".ClaimActivity" android:exported="true"
        android:theme="@android:style/Theme.DeviceDefault.Dialog"/>
  </application>
</manifest>
```

`res/xml/probe.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowsChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:accessibilityFlags="flagRetrieveInteractiveWindows"
    android:canRetrieveWindowContent="true"
    android:notificationTimeout="200"/>
```

`src/probe/a11y/ProbeService.java`:
```java
package probe.a11y;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Rect;
import android.util.Log;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;

/** Logs every window getWindows() returns, top first, on each window change. */
public class ProbeService extends AccessibilityService {
    @Override public void onAccessibilityEvent(AccessibilityEvent e) {
        StringBuilder b = new StringBuilder("windows:");
        for (AccessibilityWindowInfo w : getWindows()) {
            AccessibilityNodeInfo root = w.getRoot();
            Rect r = new Rect();
            w.getBoundsInScreen(r);
            b.append("\n  type=").append(w.getType())
             .append(" layer=").append(w.getLayer())
             .append(" focused=").append(w.isFocused()).append(" bounds=").append(r.toShortString())
             .append(" title=").append(w.getTitle())
             .append(" rootPackage=").append(root == null ? "(no root)" : root.getPackageName())
             .append(" rootDesc=").append(root == null ? "" : root.getContentDescription());
        }
        Log.i("A11YPROBE", b.toString());
    }

    @Override public void onInterrupt() {}
}
```

`src/probe/a11y/ClaimActivity.java`:
```java
package probe.a11y;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.accessibility.AccessibilityNodeInfo;
import android.widget.Button;

/** A dialog whose window tells accessibility it belongs to the package named in the "as" extra. */
public class ClaimActivity extends Activity {
    @Override protected void onCreate(Bundle s) {
        super.onCreate(s);
        final String as = getIntent().getStringExtra("as");
        setTitle("Claim");
        Button cancel = new Button(this);
        cancel.setText("Cancel");
        setContentView(cancel);
        View.AccessibilityDelegate claim = new View.AccessibilityDelegate() {
            @Override public void onInitializeAccessibilityNodeInfo(View host, AccessibilityNodeInfo info) {
                super.onInitializeAccessibilityNodeInfo(host, info);
                if (as != null) {
                    info.setPackageName(as);
                    info.setContentDescription("claims " + info.getPackageName());
                }
            }
        };
        getWindow().getDecorView().setAccessibilityDelegate(claim);
        cancel.setAccessibilityDelegate(claim);
    }
}
```
