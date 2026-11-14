package io.github.zlkiki.einkscreens;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;

/**
 * su 명령 실행 도우미.
 * 명령마다 su를 새로 띄우면 Magisk가 매번 "슈퍼유저 허용" 알림을 띄우므로,
 * su 셸 하나를 열어 두고 재사용함 (알림은 앱 실행당 한 번).
 */
final class Root {
    static final class Result {
        final int code;
        final String out;
        Result(int code, String out) { this.code = code; this.out = out; }
        boolean ok() { return code == 0; }
    }

    /** 열어 둔 su 셸 하나. 명령은 서브셸로 감싸 exit가 셸을 끝내지 않게 함. */
    private static final class Shell {
        final String[] argv;
        Process p;
        OutputStream in;
        BufferedReader out;
        int seq;

        Shell(String... argv) { this.argv = argv; }

        synchronized Result run(String cmd) {
            for (int attempt = 0; attempt < 2; attempt++) {
                try {
                    if (p == null) start();
                    String end = "__EINK_END_" + (++seq) + "__";
                    in.write(("(\n" + cmd + "\n) </dev/null 2>&1; echo \"" + end + "$?\"\n").getBytes("UTF-8"));
                    in.flush();
                    StringBuilder sb = new StringBuilder();
                    String line;
                    while ((line = out.readLine()) != null) {
                        int i = line.indexOf(end);
                        if (i >= 0) {
                            sb.append(line, 0, i);
                            return new Result(Integer.parseInt(line.substring(i + end.length()).trim()), sb.toString().trim());
                        }
                        sb.append(line).append('\n');
                    }
                    throw new Exception("su shell closed");
                } catch (Exception e) {
                    close();
                    if (attempt == 1) return new Result(-1, String.valueOf(e));
                }
            }
            return new Result(-1, "unreachable");
        }

        void start() throws Exception {
            p = new ProcessBuilder(argv).redirectErrorStream(true).start();
            in = p.getOutputStream();
            out = new BufferedReader(new InputStreamReader(p.getInputStream(), "UTF-8"));
        }

        void close() {
            if (p != null) p.destroy();
            p = null;
        }
    }

    private static final Shell SH = new Shell("su");
    private static Shell global;

    private Root() {}

    static Result run(String cmd) {
        return SH.run(cmd);
    }

    /** 전역 마운트 네임스페이스에서 실행 (Magisk su --mount-master). 필요할 때만 열림. */
    static synchronized Result runGlobal(String cmd) {
        if (global == null) global = new Shell("su", "--mount-master");
        return global.run(cmd);
    }

    static boolean available() {
        Result r = run("id");
        return r.ok() && r.out.contains("uid=0");
    }

    /** 셸 인자용 작은따옴표 감싸기. */
    static String q(String s) {
        return "'" + s.replace("'", "'\\''") + "'";
    }
}
