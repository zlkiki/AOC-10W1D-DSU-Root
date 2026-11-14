package io.github.zlkiki.einkscreens;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

public class MainActivity extends Activity {
    static final String LOGO_DEV = "/dev/block/by-name/logo";
    static final String EINK = "/data/misc/eink";
    static final String BACKUP_DIR = "/sdcard/EinkScreens/backup";
    static final String BACKUP_LOGO = BACKUP_DIR + "/logo_original.img";

    static final int SLEEP = 0, POWEROFF = 1, BOOTLOGO = 2, BOOTANIM = 3, CHARGE = 4;
    static final String[] SLEEP_FILES = {"standby", "standby_charge", "standby_charge_full", "standby_lowpower"};
    static final String[] OFF_FILES = {"poweroff", "poweroff_nopower"};

    final boolean ko = Locale.getDefault().getLanguage().equals("ko");
    final ImageView[] thumbs = new ImageView[5];
    final List<Button> buttons = new ArrayList<>();
    TextView status;
    CheckBox crop;
    volatile boolean busy;
    boolean rooted;

    String t(String k, String e) { return ko ? k : e; }

    // ---------------------------------------------------------------- UI

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(Color.WHITE);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(36, 36, 36, 60);
        sv.addView(root);

        TextView title = text(t("E-Ink 화면 바꾸기", "E-Ink Screens"), 34, true);
        root.addView(title);
        status = text(t("확인 중…", "Checking…"), 20, false);
        status.setPadding(0, 12, 0, 12);
        root.addView(status);
        crop = new CheckBox(this);
        crop.setText(t("사진을 잘라서 화면을 꽉 채우기 (끄면 전체가 보이고 남는 곳은 흰색)",
                "Crop photo to fill the screen (off: show whole photo on white)"));
        crop.setTextSize(18);
        crop.setTextColor(Color.BLACK);
        crop.setChecked(true);
        root.addView(crop);

        addSlot(root, SLEEP, t("슬립 화면", "Sleep screen"),
                t("전원 버튼을 짧게 눌러 잠들 때", "When you press power briefly to sleep"));
        addSlot(root, POWEROFF, t("종료 화면", "Power-off screen"),
                t("전원을 끈 뒤 남는 화면", "Left on screen after power-off"));
        addSlot(root, BOOTLOGO, t("부팅 로고", "Boot logo"),
                t("전원을 켜면 처음 나오는 화면 2장 (재부팅해야 보임)", "First two screens at power-on (visible after reboot)"));
        addSlot(root, BOOTANIM, t("부팅 애니메이션", "Boot animation"),
                t("부팅 로고 다음, 진행 막대가 채워지는 화면 (재부팅해야 보임)", "Progress-bar screen after the logo (visible after reboot)"));
        addSlot(root, CHARGE, t("꺼진 상태 충전 화면", "Off-charging screens"),
                t("꺼진 상태에서 충전기를 꽂았을 때 (배터리 칸이 자동으로 그려짐)", "When charging while powered off (battery bars are drawn for you)"));

        LinearLayout row = new LinearLayout(this);
        row.setPadding(0, 30, 0, 0);
        row.addView(button(t("슬립 해보기", "Try sleep"), v -> work(() -> {
            Root.run("input keyevent 26");
            return null;
        })));
        row.addView(button(t("재부팅", "Reboot"), v -> new AlertDialog.Builder(this)
                .setMessage(t("지금 재부팅할까요?", "Reboot now?"))
                .setPositiveButton(t("재부팅", "Reboot"), (d, w) -> work(() -> {
                    Root.run("svc power reboot || reboot");
                    return null;
                }))
                .setNegativeButton(t("취소", "Cancel"), null).show()));
        root.addView(row);
        TextView info = text(t("처음 실행할 때 원래 logo 파티션을 " + BACKUP_LOGO + " 에 백업합니다. PC에도 복사해 두세요.",
                "On first run the original logo partition is backed up to " + BACKUP_LOGO + ". Copy it to your PC too."), 16, false);
        info.setPadding(0, 24, 0, 0);
        root.addView(info);
        setContentView(sv);
        work(this::init);
    }

    void addSlot(LinearLayout parent, int slot, String name, String desc) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.HORIZONTAL);
        card.setPadding(0, 28, 0, 28);
        ImageView iv = new ImageView(this);
        iv.setLayoutParams(new LinearLayout.LayoutParams(234, 312));
        iv.setBackgroundColor(Color.rgb(230, 230, 230));
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        thumbs[slot] = iv;
        card.addView(iv);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(28, 0, 0, 0);
        col.addView(text(name, 26, true));
        col.addView(text(desc, 17, false));
        LinearLayout btns = new LinearLayout(this);
        btns.setPadding(0, 16, 0, 0);
        btns.addView(button(t("사진 고르기", "Pick photo"), v -> pick(slot)));
        btns.addView(button(t("순정으로", "Restore stock"), v -> new AlertDialog.Builder(this)
                .setMessage(name + ": " + t("순정 화면으로 되돌릴까요?", "restore the stock screen?"))
                .setPositiveButton(t("되돌리기", "Restore"), (d, w) -> work(() -> restore(slot)))
                .setNegativeButton(t("취소", "Cancel"), null).show()));
        col.addView(btns);
        card.addView(col);
        parent.addView(card);
        View line = new View(this);
        line.setBackgroundColor(Color.BLACK);
        line.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 2));
        parent.addView(line);
    }

    TextView text(String s, int sp, boolean bold) {
        TextView tv = new TextView(this);
        tv.setText(s);
        tv.setTextSize(sp);
        tv.setTextColor(Color.BLACK);
        if (bold) tv.setTypeface(Typeface.DEFAULT_BOLD);
        return tv;
    }

    Button button(String s, View.OnClickListener l) {
        Button b = new Button(this);
        b.setText(s);
        b.setTextSize(18);
        b.setAllCaps(false);
        b.setOnClickListener(v -> { if (!busy) l.onClick(v); });
        buttons.add(b);
        return b;
    }

    void setStatus(String s) { runOnUiThread(() -> status.setText(s)); }

    interface Job { String run() throws Exception; }

    /** 백그라운드 작업. 반환 문자열을 상태 줄에 표시. */
    void work(Job job) {
        if (busy) return;
        busy = true;
        setStatus(t("작업 중… 화면을 끄지 마세요", "Working… keep the screen on"));
        new Thread(() -> {
            String msg;
            try {
                msg = job.run();
            } catch (Throwable e) {
                msg = t("실패: ", "Failed: ") + e.getMessage();
            }
            busy = false;
            if (msg != null) setStatus(msg);
        }).start();
    }

    // ---------------------------------------------------------------- 시작

    String init() throws Exception {
        rooted = Root.available();
        if (!rooted)
            return t("루트 권한이 없습니다. Magisk가 설치돼 있어야 하고, 팝업이 뜨면 [허용]을 누르세요. "
                    + "팝업을 놓쳤다면 Magisk 앱 > 슈퍼유저에서 이 앱을 켜고 다시 실행하세요.",
                    "No root. Magisk is required; tap Grant on the popup. "
                    + "If you missed it, enable this app in Magisk > Superuser and reopen.");
        StringBuilder sb = new StringBuilder();
        if (!"AOC_10W1D".equals(Build.MODEL))
            sb.append(t("⚠ 검증된 기기(AOC_10W1D)가 아닙니다: ", "⚠ Not the verified device (AOC_10W1D): ")).append(Build.MODEL).append('\n');
        Logo cur = readLogo();
        if (!exists(BACKUP_LOGO)) {
            File tmp = tmpFile("logo_cur.img");
            write(tmp, cur.data);
            Root.Result r = Root.run("mkdir -p " + BACKUP_DIR + " && cp " + Root.q(tmp.getPath()) + " " + BACKUP_LOGO
                    + " && sha256sum " + BACKUP_LOGO + " > " + BACKUP_LOGO + ".sha256");
            if (!r.ok()) throw new Exception("backup: " + r.out);
            sb.append(t("원래 logo를 백업했습니다: ", "Backed up original logo: ")).append(BACKUP_LOGO).append('\n');
        }
        refresh(cur);
        sb.append(t("준비 완료. 바꿀 화면의 [사진 고르기]를 누르세요.", "Ready. Tap Pick photo on a screen to change it."));
        return sb.toString();
    }

    // ---------------------------------------------------------------- 사진 선택·적용

    // 이 펌웨어는 DocumentsUI가 없고, 순정 갤러리(com.wetao.gallery)는 GET_CONTENT를 받으면 종료됨.
    // 그래서 루트로 사진 폴더를 직접 찾아 보여 주는 앱 내 선택 화면을 기본으로 씀.
    static final String FIND_IMAGES = "find /sdcard/Pictures/ /sdcard/DCIM/ /sdcard/Download/ -maxdepth 5 -type f"
            + " \\( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' -o -iname '*.bmp' \\)"
            + " -not -path '*/Android/*' -not -path '*/.*' -size +1k 2>/dev/null | sort";
    static final int MAX_THUMBS = 60;

    void pick(int slot) {
        if (!rooted) { setStatus(t("루트 권한이 필요합니다.", "Root required.")); return; }
        work(() -> {
            Map<String, List<String>> dirs = new TreeMap<>();
            for (String f : Root.run(FIND_IMAGES).out.split("\n")) {
                f = f.trim();
                int s = f.lastIndexOf('/');
                if (s <= 0) continue;
                String d = f.substring(0, s);
                if (!dirs.containsKey(d)) dirs.put(d, new ArrayList<>());
                dirs.get(d).add(f);
            }
            runOnUiThread(() -> showFolders(slot, dirs));
            return dirs.isEmpty() ? t("사진을 찾지 못했습니다. 사진을 기기의 Pictures 폴더에 넣어 주세요.",
                    "No photos found. Put photos in the Pictures folder.")
                    : t("사진이 있는 폴더를 고르세요.", "Choose a folder.");
        });
    }

    void showFolders(int slot, Map<String, List<String>> dirs) {
        List<String> keys = new ArrayList<>(dirs.keySet());
        String[] items = new String[keys.size() + 1];
        for (int i = 0; i < keys.size(); i++) {
            String k = keys.get(i);
            String shown = k.replaceFirst("^/sdcard/+", "");
            items[i] = (shown.isEmpty() ? "/" : shown) + "  (" + dirs.get(k).size() + ")";
        }
        items[keys.size()] = t("다른 앱으로 고르기…", "Pick with another app…");
        new AlertDialog.Builder(this)
                .setTitle(t("사진 폴더", "Photo folders"))
                .setItems(items, (d, w) -> {
                    if (w == keys.size()) pickExternal(slot);
                    else loadThumbs(slot, dirs.get(keys.get(w)));
                })
                .setNegativeButton(t("취소", "Cancel"), null).show();
    }

    void loadThumbs(int slot, List<String> files) {
        work(() -> {
            List<String> shown = files.size() > MAX_THUMBS ? files.subList(0, MAX_THUMBS) : files;
            List<Bitmap> thumbs = new ArrayList<>();
            for (String f : shown) {
                Bitmap b = null;
                try { b = decodeBytes(readRoot(f), 180, 240); } catch (Exception ignored) {}
                thumbs.add(b);
            }
            runOnUiThread(() -> showImages(slot, shown, thumbs));
            return files.size() > MAX_THUMBS
                    ? t("사진이 많아 앞의 " + MAX_THUMBS + "장만 보여 줍니다.", "Showing the first " + MAX_THUMBS + " photos.")
                    : t("바꿀 사진을 누르세요.", "Tap a photo.");
        });
    }

    void showImages(int slot, List<String> files, List<Bitmap> thumbs) {
        ScrollView sv = new ScrollView(this);
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setPadding(16, 16, 16, 16);
        sv.addView(col);
        AlertDialog[] dlg = new AlertDialog[1];
        LinearLayout row = null;
        for (int i = 0; i < files.size(); i++) {
            if (i % 3 == 0) {
                row = new LinearLayout(this);
                col.addView(row);
            }
            String f = files.get(i);
            LinearLayout cell = new LinearLayout(this);
            cell.setOrientation(LinearLayout.VERTICAL);
            cell.setPadding(10, 10, 10, 18);
            cell.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1));
            ImageView iv = new ImageView(this);
            iv.setLayoutParams(new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 300));
            iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
            iv.setBackgroundColor(Color.WHITE);
            if (thumbs.get(i) != null) iv.setImageBitmap(thumbs.get(i));
            cell.addView(iv);
            TextView name = text(f.substring(f.lastIndexOf('/') + 1), 15, false);
            name.setGravity(Gravity.CENTER);
            cell.addView(name);
            cell.setOnClickListener(v -> {
                dlg[0].dismiss();
                boolean fill = crop.isChecked();
                work(() -> apply(slot, Img.fitPortrait(decodeBytes(readRoot(f), Img.W, Img.H), fill)));
            });
            row.addView(cell);
        }
        dlg[0] = new AlertDialog.Builder(this)
                .setView(sv)
                .setNegativeButton(t("취소", "Cancel"), null).show();
    }

    void pickExternal(int slot) {
        Intent i = new Intent(Intent.ACTION_GET_CONTENT);
        i.setType("image/*");
        i.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(Intent.createChooser(i, t("사진 선택", "Choose photo")), 100 + slot);
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (res != RESULT_OK || data == null || data.getData() == null || req < 100) return;
        int slot = req - 100;
        Uri uri = data.getData();
        boolean fill = crop.isChecked();
        work(() -> apply(slot, Img.fitPortrait(decode(uri), fill)));
    }

    String apply(int slot, Bitmap p) throws Exception {
        switch (slot) {
            case SLEEP:
                putEink(SLEEP_FILES, p);
                refresh(null);
                return t("슬립 화면을 바꿨습니다. [슬립 해보기]로 확인하세요.", "Sleep screen changed. Use Try sleep to check.");
            case POWEROFF: {
                putEink(OFF_FILES, p);
                Logo l = readLogo();
                l.put(Logo.T_POWEROFF, p);
                writeLogo(l);
                refresh(l);
                return t("종료 화면을 바꿨습니다.", "Power-off screen changed.");
            }
            case BOOTLOGO: {
                Logo l = readLogo();
                l.put(Logo.T_UBOOT, p);
                l.put(Logo.T_KERNEL, p);
                writeLogo(l);
                refresh(l);
                return t("부팅 로고를 바꿨습니다. 재부팅하면 보입니다.", "Boot logo changed. Reboot to see it.");
            }
            case CHARGE: {
                Logo l = readLogo();
                for (int i = 0; i < Logo.T_CHARGE.length; i++)
                    l.put(Logo.T_CHARGE[i], Img.withBattery(p, i, false));
                l.put(Logo.T_LOWPOWER, Img.withBattery(p, 0, true));
                writeLogo(l);
                refresh(l);
                return t("충전 화면을 바꿨습니다. 전원을 끈 뒤 충전기를 꽂으면 보입니다.",
                        "Charging screens changed. Power off and plug in the charger to see them.");
            }
            case BOOTANIM: {
                File zip = tmpFile("bootanimation.zip");
                BootAnim.writeZip(p, zip);
                File prop = tmpFile("module.prop"), sh = tmpFile("post-fs-data.sh");
                write(prop, BootAnim.MODULE_PROP.getBytes("UTF-8"));
                write(sh, BootAnim.POST_FS_DATA.getBytes("UTF-8"));
                String d = BootAnim.MODDIR;
                Root.Result r = Root.run("mkdir -p " + d + " && cp " + Root.q(zip.getPath()) + " " + d + "/bootanimation.zip"
                        + " && cp " + Root.q(prop.getPath()) + " " + d + "/module.prop"
                        + " && cp " + Root.q(sh.getPath()) + " " + d + "/post-fs-data.sh"
                        + " && chmod 0644 " + d + "/bootanimation.zip " + d + "/module.prop && chmod 0755 " + d + "/post-fs-data.sh"
                        + " && rm -f " + d + "/disable " + d + "/remove");
                if (!r.ok()) throw new Exception(r.out);
                // 같은 파일을 덮는 다른 모듈은 꺼 둠 (지우지는 않음, Magisk 앱에서 다시 켤 수 있음)
                List<String> off = new ArrayList<>();
                for (String[] m : otherAnimModules())
                    if (m[1].equals("active") && Root.run("touch " + Root.q(m[0] + "/disable")).ok()) off.add(name(m[0]));
                refresh(null);
                return t("부팅 애니메이션을 준비했습니다. 재부팅하면 보입니다.", "Boot animation ready. Reboot to see it.")
                        + (off.isEmpty() ? "" : t("\n겹치는 다른 모듈을 껐습니다: ", "\nDisabled conflicting module(s): ") + off);
            }
        }
        return null;
    }

    String restore(int slot) throws Exception {
        switch (slot) {
            case SLEEP:
                rmEink(SLEEP_FILES);
                refresh(null);
                return t("슬립 화면을 순정으로 되돌렸습니다.", "Sleep screen restored.");
            case POWEROFF: {
                rmEink(OFF_FILES);
                Logo l = readLogo();
                l.copyFrom(backupLogo(), Logo.T_POWEROFF);
                writeLogo(l);
                refresh(l);
                return t("종료 화면을 순정으로 되돌렸습니다.", "Power-off screen restored.");
            }
            case BOOTLOGO: {
                Logo l = readLogo(), b = backupLogo();
                l.copyFrom(b, Logo.T_UBOOT);
                l.copyFrom(b, Logo.T_KERNEL);
                writeLogo(l);
                refresh(l);
                return t("부팅 로고를 백업본으로 되돌렸습니다.", "Boot logo restored from backup.");
            }
            case CHARGE: {
                Logo l = readLogo(), b = backupLogo();
                for (int ty : Logo.T_CHARGE) l.copyFrom(b, ty);
                l.copyFrom(b, Logo.T_LOWPOWER);
                writeLogo(l);
                refresh(l);
                return t("충전 화면을 백업본으로 되돌렸습니다.", "Charging screens restored from backup.");
            }
            case BOOTANIM: {
                Root.Result r = Root.run("rm -rf " + BootAnim.MODDIR);
                if (!r.ok()) throw new Exception(r.out);
                // 같은 파일을 덮는 다른 모듈(예: 수동 설치 모듈)도 삭제 표시 → 다음 부팅 때 Magisk가 지움
                List<String> rm = new ArrayList<>();
                for (String[] m : otherAnimModules())
                    if (!m[1].equals("remove") && Root.run("touch " + Root.q(m[0] + "/remove")).ok()) rm.add(name(m[0]));
                // 지금 걸린 덮어쓰기도 바로 풂 (실패해도 재부팅하면 순정)
                Root.runGlobal(BootAnim.UNMOUNT);
                Root.run(BootAnim.UNMOUNT);
                refresh(null);
                return t("부팅 애니메이션을 순정으로 되돌렸습니다. 재부팅하면 순정 애니메이션이 나옵니다.",
                        "Boot animation restored. Reboot to see the stock animation.")
                        + (rm.isEmpty() ? "" : t("\n같은 화면을 바꾸던 다른 모듈도 삭제 표시했습니다: ",
                        "\nAlso marked for removal: ") + rm);
            }
        }
        return null;
    }

    // ---------------------------------------------------------------- 슬립·종료 (/data/misc/eink)

    void putEink(String[] names, Bitmap portrait) throws Exception {
        Bitmap stored = Img.rotateCw(Img.grayBitmap(portrait));
        File tmp = tmpFile("eink.png");
        try (FileOutputStream o = new FileOutputStream(tmp)) {
            stored.compress(Bitmap.CompressFormat.PNG, 100, o);
        }
        StringBuilder c = new StringBuilder();
        c.append("d=" + EINK + "; [ -d $d ] || { mkdir -p $d && chown system:system $d && chmod 0770 $d && chcon u:object_r:rk_eink_data_file:s0 $d; } || exit 1; ");
        for (String n : names) {
            String f = "$d/" + n + ".png";
            c.append("cp ").append(Root.q(tmp.getPath())).append(' ').append(f)
                    .append(" && chown system:system ").append(f)
                    .append(" && chmod 0644 ").append(f)
                    .append(" && chcon u:object_r:rk_eink_data_file:s0 ").append(f).append(" || exit 1; ");
        }
        Root.Result r = Root.run(c.toString());
        if (!r.ok()) throw new Exception(r.out);
    }

    void rmEink(String[] names) {
        StringBuilder c = new StringBuilder();
        for (String n : names) c.append("rm -f ").append(EINK).append('/').append(n).append(".png; ");
        Root.run(c.toString());
    }

    // ---------------------------------------------------------------- logo 파티션

    Logo readLogo() throws Exception {
        Root.Result sz = Root.run("blockdev --getsize64 " + LOGO_DEV);
        if (!sz.ok() || !sz.out.trim().equals(String.valueOf(Logo.PART_SIZE)))
            throw new Exception(t("logo 파티션 크기가 예상과 다릅니다: ", "unexpected logo partition size: ") + sz.out);
        return new Logo(readRoot(LOGO_DEV));
    }

    Logo backupLogo() throws Exception {
        if (!exists(BACKUP_LOGO)) throw new Exception(t("백업이 없습니다: ", "no backup: ") + BACKUP_LOGO);
        return new Logo(readRoot(BACKUP_LOGO));
    }

    void writeLogo(Logo l) throws Exception {
        File tmp = tmpFile("logo_new.img");
        write(tmp, l.data);
        String want = Logo.sha256(l.data);
        Root.Result r = Root.run("dd if=" + Root.q(tmp.getPath()) + " of=" + LOGO_DEV + " bs=1048576 conv=fsync 2>&1"
                + " && sync && echo 3 > /proc/sys/vm/drop_caches && sha256sum " + LOGO_DEV);
        if (!r.ok() || !r.out.contains(want))
            throw new Exception(t("logo 기록 검증 실패: ", "logo write verify failed: ") + r.out);
        tmp.delete();
    }

    // ---------------------------------------------------------------- 미리보기

    void refresh(Logo logo) {
        try {
            if (logo == null) logo = readLogo();
            final Bitmap boot = Img.thumb(logo.render(Logo.T_UBOOT), 312);
            final Bitmap chg = Img.thumb(logo.render(Logo.T_CHARGE[3]), 312);
            final Bitmap sl = einkThumb("standby");
            final Bitmap off = einkThumb("poweroff");
            final Bitmap ani = animThumb();
            runOnUiThread(() -> {
                thumbs[BOOTLOGO].setImageBitmap(boot);
                thumbs[CHARGE].setImageBitmap(chg);
                thumbs[SLEEP].setImageBitmap(sl);
                thumbs[POWEROFF].setImageBitmap(off);
                thumbs[BOOTANIM].setImageBitmap(ani);
            });
        } catch (Exception e) {
            setStatus(t("미리보기 실패: ", "Preview failed: ") + e.getMessage());
        }
    }

    Bitmap einkThumb(String name) throws Exception {
        String user = EINK + "/" + name + ".png";
        String src = exists(user) ? user : "/vendor/media/" + name + ".png";
        byte[] d = readRoot(src);
        Bitmap b = BitmapFactory.decodeByteArray(d, 0, d.length);
        return b == null ? null : Img.thumb(Img.rotateCcw(b), 312);
    }

    /** 다음 부팅 때 실제로 쓰일 애니메이션 zip을 미리보기. */
    Bitmap animThumb() throws Exception {
        String src = null;
        String own = BootAnim.MODDIR;
        if (exists(own + "/bootanimation.zip") && !exists(own + "/disable") && !exists(own + "/remove"))
            src = own + "/bootanimation.zip";
        if (src == null)
            for (String[] m : otherAnimModules())
                if (m[1].equals("active") && exists(m[0] + "/bootanimation.zip")) { src = m[0] + "/bootanimation.zip"; break; }
        if (src == null) {
            // 순정: 아직 덮어쓰기가 걸려 있으면 순정 파일이 가려져 있으므로 미리보기 생략
            if (Root.run("grep -q ' " + BootAnim.TARGET + " ' /proc/self/mounts").ok()) return null;
            src = BootAnim.TARGET;
        }
        File tmp = tmpFile("anim_cur.zip");
        write(tmp, readRoot(src));
        try (ZipFile z = new ZipFile(tmp)) {
            List<String> names = new ArrayList<>();
            for (Enumeration<? extends ZipEntry> en = z.entries(); en.hasMoreElements(); ) {
                String n = en.nextElement().getName();
                if (n.endsWith(".png")) names.add(n);
            }
            if (names.isEmpty()) return null;
            Collections.sort(names);
            String n = names.get(names.size() / 2);
            try (InputStream in = z.getInputStream(z.getEntry(n))) {
                Bitmap b = BitmapFactory.decodeStream(in);
                return b == null ? null : Img.thumb(b, 312);
            }
        }
    }

    // ---------------------------------------------------------------- 파일 도우미

    /** {모듈 폴더, active|disabled|remove} 목록. */
    List<String[]> otherAnimModules() {
        List<String[]> list = new ArrayList<>();
        Root.Result r = Root.run(BootAnim.FIND_OTHERS);
        for (String line : r.out.split("\n")) {
            int sp = line.lastIndexOf(' ');
            if (sp > 0 && line.startsWith("/data/adb/modules/")) list.add(new String[]{line.substring(0, sp), line.substring(sp + 1)});
        }
        return list;
    }

    static String name(String dir) {
        return dir.substring(dir.lastIndexOf('/') + 1);
    }

    boolean exists(String path) {
        return Root.run("[ -f " + Root.q(path) + " ]").ok();
    }

    File tmpFile(String name) {
        return new File(getCacheDir(), name);
    }

    /** 루트로 파일/블록 장치를 읽음: 앱이 만든 빈 파일에 root가 내용을 씀(소유자·레이블 유지). */
    byte[] readRoot(String path) throws Exception {
        File tmp = tmpFile("read.bin");
        write(tmp, new byte[0]);
        Root.Result r = Root.run("cat " + Root.q(path) + " > " + Root.q(tmp.getPath()));
        if (!r.ok()) throw new Exception(path + ": " + r.out);
        byte[] d = readFile(tmp);
        tmp.delete();
        return d;
    }

    static void write(File f, byte[] d) throws Exception {
        try (FileOutputStream o = new FileOutputStream(f)) { o.write(d); }
    }

    static byte[] readFile(File f) throws Exception {
        try (FileInputStream in = new FileInputStream(f)) { return readAll(in); }
    }

    static byte[] readAll(InputStream in) throws Exception {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        byte[] buf = new byte[1 << 16];
        int n;
        while ((n = in.read(buf)) > 0) b.write(buf, 0, n);
        return b.toByteArray();
    }

    /** 바이트에서 디코딩. 가로·세로가 minW·minH 이상 남는 한 2배씩 줄여 메모리 절약. */
    Bitmap decodeBytes(byte[] d, int minW, int minH) throws Exception {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(d, 0, d.length, o);
        int s = 1;
        while (o.outWidth / (s * 2) >= minW && o.outHeight / (s * 2) >= minH) s *= 2;
        BitmapFactory.Options o2 = new BitmapFactory.Options();
        o2.inSampleSize = s;
        Bitmap b = BitmapFactory.decodeByteArray(d, 0, d.length, o2);
        if (b == null) throw new Exception(t("사진을 열 수 없습니다", "cannot open photo"));
        return b;
    }

    Bitmap decode(Uri uri) throws Exception {
        BitmapFactory.Options o = new BitmapFactory.Options();
        o.inJustDecodeBounds = true;
        try (InputStream in = getContentResolver().openInputStream(uri)) { BitmapFactory.decodeStream(in, null, o); }
        int s = 1;
        while (o.outWidth / (s * 2) >= Img.W && o.outHeight / (s * 2) >= Img.H) s *= 2;
        BitmapFactory.Options o2 = new BitmapFactory.Options();
        o2.inSampleSize = s;
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            Bitmap b = BitmapFactory.decodeStream(in, null, o2);
            if (b == null) throw new Exception(t("사진을 열 수 없습니다", "cannot open photo"));
            return b;
        }
    }
}
