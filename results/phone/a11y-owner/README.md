# Can an app on the phone itself see which app owns a window? (31 Oct 2026, $0)

The gate in `phone/` runs on a computer and reads each window's owner from Android's input dispatcher over adb, keyed by
the uid Android assigns to each app. Reading that list needs the DUMP permission, which on this emulator is
`prot=signature|privileged|development` (`adb shell dumpsys package android`): installing an app does not grant it. An app
on the phone can run an accessibility service instead. Its window list (`AccessibilityWindowInfo`) carries no package and no uid
(`android/view/accessibility/AccessibilityWindowInfo.java`; every file named here is from the SDK's android-36 sources): the only app name it offers is the
package name on the window's root node, and that node is built inside the app that drew the window (`View.java:11470`,
`info.setPackageName(mContext.getPackageName())`). Two questions, tested on the emulator (Small_Phone, API 36) with the
probe app below, which logs every window `getWindows()` returns:

**1. Does the service see an attacker's dialog, and name its app?** GhostEI case 26's "System Update Required" dialog,
fired over Clock:
```
# GhostEI case 26's dialog over Clock; the probe service's view, then the input dispatcher's (31 Oct 2026, emulator-5554, API 36)
10-31 15:57:14.392 17523 17523 I A11YPROBE: windows:
10-31 15:57:14.392 17523 17523 I A11YPROBE:   type=3 layer=1 focused=false bounds=[0,0][720,48] title=null rootPackage=com.android.systemui
10-31 15:57:14.392 17523 17523 I A11YPROBE:   type=3 layer=0 focused=true bounds=[0,0][720,1280] title=null rootPackage=com.example.myapplication
# adb shell dumpsys input
    displayId=0, name='f931918 Sys2038:com.example.myapplication/com.example.myapplication.PopupActivity'
```
Yes: the dialog is the focused full-screen window and its root node names `com.example.myapplication`, GhostEI's
helper; the input dispatcher names the same app (window type 2038, `TYPE_APPLICATION_OVERLAY`: `WindowManager.java:2350`,
`:2640`). Clock's window is not in the list while the dialog covers it: `getWindows()` returns only the windows a user can
interact with (`AccessibilityService.java:1051`). This run's log line predates the `rootDesc` field in the probe below.

**2. Can an app make its window claim another app's name?** The probe's `ClaimActivity`, a dialog over Clock, sets
`com.google.android.deskclock` as the package on its own nodes, and writes the name it reads back into its description:
```
10-31 15:58:28.896 17789 17789 I A11YPROBE: windows:
10-31 15:58:28.896 17789 17789 I A11YPROBE:   type=3 layer=1 focused=false bounds=[0,0][720,48] title=null rootPackage=com.android.systemui rootDesc=null
10-31 15:58:28.896 17789 17789 I A11YPROBE:   type=1 layer=0 focused=true bounds=[40,515][680,765] title=Claim rootPackage=probe.a11y rootDesc=claims com.google.android.deskclock
```
No: inside the app the name was set (the description reads "claims com.google.android.deskclock"), but the service
received `probe.a11y`, the app's own. Before a node reaches a service, Android checks its package against the packages of
the uid that owns the window and replaces any other name with that uid's own
(`AccessibilityInteractionClient.java:1451-1463`). In an earlier run of the same test, without the description,
uiautomator, which reads the same nodes, reported `package="probe.a11y"` on the dialog's Cancel button, and the gate in
`phone/` judged a tap at its centre a block (owner `probe.a11y`, not the task app); no tap was sent.

**What this shows:** an accessibility service running on the phone can name the app that owns the window in front, from
a name Android checks against that window's uid. That is the owner check this gate needs, without a computer.
**Not checked:** a physical phone; the case the source leaves open ("Empty array means any package name is Okay": when
Android sends no list, no name is replaced); windows a user cannot interact with, which `getWindows()` leaves out;
whether Google Play accepts an accessibility service used this way. No on-phone version of the gate is built.

**Rerun:** build the probe with the SDK's build tools (aapt2, javac against `platforms/android-36/android.jar`, d8,
zipalign, apksigner), install it on the emulator, enable it with
`adb -s emulator-5554 shell settings put secure enabled_accessibility_services probe.a11y/.ProbeService` and
`... accessibility_enabled 1`, and read `adb logcat -s A11YPROBE:I`. Test 2:
`adb shell am start -n probe.a11y/.ClaimActivity --es as com.google.android.deskclock` over Clock. Afterwards:
`settings delete secure enabled_accessibility_services`, `accessibility_enabled 0`, `adb uninstall probe.a11y`.

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
