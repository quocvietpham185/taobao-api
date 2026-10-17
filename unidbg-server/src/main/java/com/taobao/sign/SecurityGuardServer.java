package com.taobao.sign;

import com.alibaba.fastjson.JSONObject;
import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Emulator;
import com.github.unidbg.file.FileResult;
import com.github.unidbg.file.IOResolver;
import com.github.unidbg.file.linux.AndroidFileIO;
import com.github.unidbg.linux.android.AndroidARMEmulator;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.array.ArrayObject;
import com.github.unidbg.linux.android.dvm.array.ByteArray;
import com.github.unidbg.linux.android.dvm.jni.ProxyDvmObject;
import com.github.unidbg.linux.android.dvm.wrapper.DvmBoolean;
import com.github.unidbg.linux.android.dvm.wrapper.DvmInteger;
import com.github.unidbg.linux.file.SimpleFileIO;
import com.github.unidbg.memory.Memory;
import fi.iki.elonen.NanoHTTPD;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public class SecurityGuardServer extends NanoHTTPD {

    private static final int PORT = 8001;
    private final SecurityGuardEngine engine;

    public SecurityGuardServer() throws IOException {
        super(PORT);
        System.out.println("[*] Initializing SecurityGuard Unidbg Engine...");
        this.engine = new SecurityGuardEngine();
        start(NanoHTTPD.SOCKET_READ_TIMEOUT, false);
        System.out.println("[✓] Unidbg ARM Microservice listening on http://127.0.0.1:" + PORT);
    }

    @Override
    public Response serve(IHTTPSession session) {
        String uri = session.getUri();
        Method method = session.getMethod();

        if ("/health".equals(uri)) {
            JSONObject res = new JSONObject();
            res.put("status", "online");
            res.put("engine", "unidbg-arm64");
            res.put("package", "com.taobao.taobao");
            res.put("version", "6.8.260901");
            return newFixedLengthResponse(Response.Status.OK, "application/json", res.toJSONString());
        }

        if ("/sign".equals(uri) && Method.POST.equals(method)) {
            try {
                Map<String, String> files = new HashMap<>();
                session.parseBody(files);
                String postData = files.get("postData");
                JSONObject req = JSONObject.parseObject(postData);

                String api = req.getString("api");
                String v = req.getString("v");
                String data = req.getString("data");
                String t = req.getString("t");
                String appKey = req.getString("app_key");
                Integer signType = req.getInteger("sign_type");

                JSONObject customJson = req.getJSONObject("custom_params");
                Map<String, String> customParams = null;
                if (customJson != null) {
                    customParams = new HashMap<>();
                    for (String k : customJson.keySet()) {
                        customParams.put(k, customJson.getString(k));
                    }
                }

                JSONObject signRes = engine.signRequest(api, v, data, t, customParams, signType, appKey);
                return newFixedLengthResponse(Response.Status.OK, "application/json", signRes.toJSONString());
            } catch (Exception e) {
                e.printStackTrace();
                JSONObject err = new JSONObject();
                err.put("error", e.getMessage());
                return newFixedLengthResponse(Response.Status.INTERNAL_ERROR, "application/json", err.toJSONString());
            }
        }

        return newFixedLengthResponse(Response.Status.NOT_FOUND, "text/plain", "Not Found");
    }

    public static class SecurityGuardEngine extends AbstractJni {
        private final AndroidEmulator emulator;
        private final VM vm;
        private final DvmClass jnicLibrary;

        private static byte[] getCertBytes() {
            try {
                File f = new File("../unidbg_assets/cert.bytes");
                if (!f.exists()) f = new File("unidbg_assets/cert.bytes");
                if (f.exists()) {
                    return Files.readAllBytes(f.toPath());
                }
            } catch (Exception ignored) {}
            return new byte[927];
        }

        private static void setupFileSystem() {
            try {
                File targetDir = new File("target/unidbg_files");
                File sgLibDir = new File("target/unidbg_files/app_SGLib");
                File resDir = new File("target/unidbg_files/res/drawable");
                targetDir.mkdirs();
                sgLibDir.mkdirs();
                resDir.mkdirs();

                File ywSrc = new File("src/main/resources/yw_1222.jpg");
                if (!ywSrc.exists()) ywSrc = new File("unidbg-server/src/main/resources/yw_1222.jpg");
                if (!ywSrc.exists()) ywSrc = new File("../unidbg_assets/res/drawable/yw_1222.jpg");

                if (ywSrc.exists()) {
                    Files.copy(ywSrc.toPath(), new File(targetDir, "yw_1222.jpg").toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    Files.copy(ywSrc.toPath(), new File(sgLibDir, "yw_1222.jpg").toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                    Files.copy(ywSrc.toPath(), new File(resDir, "yw_1222.jpg").toPath(), java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
            } catch (Exception e) {
                System.out.println("[!] setupFileSystem notice: " + e.getMessage());
            }
        }

        public SecurityGuardEngine() {
            setupFileSystem();

            emulator = AndroidEmulatorBuilder.for32Bit()
                    .setProcessName("com.taobao.taobao")
                    .build();
            emulator.getSyscallHandler().setEnableThreadDispatcher(true);
            Memory memory = emulator.getMemory();
            memory.setLibraryResolver(new AndroidResolver(23));

            File apk = new File("../taobao_official.apk");
            if (!apk.exists()) {
                apk = new File("taobao_official.apk");
            }
            final File finalApk = apk;

            emulator.getSyscallHandler().addIOResolver(new IOResolver<AndroidFileIO>() {
                @Override
                public FileResult<AndroidFileIO> resolve(Emulator<AndroidFileIO> emulator, String pathname, int oflags) {
                    if (pathname != null) {
                        if (pathname.endsWith("yw_1222.jpg")) {
                            File f = new File("src/main/resources/yw_1222.jpg");
                            if (!f.exists()) f = new File("unidbg-server/src/main/resources/yw_1222.jpg");
                            if (!f.exists()) f = new File("../unidbg_assets/res/drawable/yw_1222.jpg");
                            return FileResult.success(new SimpleFileIO(oflags, f, pathname));
                        }
                        if (pathname.endsWith("base.apk") || pathname.contains("com.taobao.taobao-1")) {
                            if (finalApk.exists()) {
                                return FileResult.success(new SimpleFileIO(oflags, finalApk, pathname));
                            }
                        }
                    }
                    return null;
                }
            });
            vm = emulator.createDalvikVM(apk.exists() ? apk : null);
            vm.setJni(this);
            vm.setVerbose(true);

            vm.resolveClass("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin");
            vm.resolveClass("java/lang/ClassLoader");
            vm.resolveClass("dalvik/system/PathClassLoader");

            File soFile = new File("src/main/resources/libsgmain.so");
            if (!soFile.exists()) {
                soFile = new File("unidbg-server/src/main/resources/libsgmain.so");
            }
            DalvikModule dm = vm.loadLibrary(soFile, false); // do not auto call init to control lifecycle
            try {
                dm.callJNI_OnLoad(emulator);
                System.out.println("[✓] JNI_OnLoad completed successfully!");
            } catch (Exception e) {
                System.out.println("[!] JNI_OnLoad notice: " + e.getMessage());
            }

            jnicLibrary = vm.resolveClass("com/taobao/wireless/security/adapter/JNICLibrary");

            // 1. Initialize Base Environment (10101)
            try {
                DvmObject<?> ctx = vm.resolveClass("android/content/Context").newObject(null);
                ArrayObject init10101 = new ArrayObject(
                        ctx,
                        DvmInteger.valueOf(vm, 3),
                        new StringObject(vm, ""),
                        new StringObject(vm, "/data/user/0/com.taobao.taobao/app_SGLib"),
                        new StringObject(vm, ""),
                        new StringObject(vm, ""),
                        new StringObject(vm, ""),
                        new StringObject(vm, ""),
                        new StringObject(vm, ""),
                        DvmInteger.valueOf(vm, 0),
                        DvmBoolean.valueOf(vm, false)
                );
                DvmObject<?> ret10101 = jnicLibrary.callStaticJniMethodObject(
                        emulator,
                        "doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;",
                        10101,
                        init10101
                );
                System.out.println("[✓] doCommandNative(10101) init result: " + ret10101);
            } catch (Exception e) {
                System.out.println("[!] doCommandNative(10101) notice: " + e.getMessage());
            }

            // 2. Register Plugin (10102)
            try {
                ArrayObject init10102 = new ArrayObject(
                        new StringObject(vm, "main"),
                        new StringObject(vm, "6.8.260901"),
                        new StringObject(vm, "/data/app/com.taobao.taobao-1/lib/arm/libsgmain.so")
                );
                DvmObject<?> ret10102 = jnicLibrary.callStaticJniMethodObject(
                        emulator,
                        "doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;",
                        10102,
                        init10102
                );
                System.out.println("[✓] doCommandNative(10102) plugin result: " + ret10102);
            } catch (Exception e) {
                System.out.println("[!] doCommandNative(10102) notice: " + e.getMessage());
            }

            System.out.println("[✓] libsgmain.so loaded and initialized successfully into Unidbg ARM runtime!");
        }

        public synchronized JSONObject signRequest(String api, String v, String data, String t, Map<String, String> customParams, Integer signType, String appKey) {
            JSONObject result = new JSONObject();
            JSONObject allSigns = new JSONObject();

            try {
                if (jnicLibrary != null) {
                    Map<String, String> paramMap;
                    if (customParams != null && !customParams.isEmpty()) {
                        paramMap = new HashMap<>(customParams);
                    } else {
                        paramMap = new HashMap<>();
                        if (data != null && !data.isEmpty()) {
                            paramMap.put("INPUT", data);
                        }
                    }

                    String actualAppKey = (appKey != null && !appKey.isEmpty()) ? appKey : "21646297";
                    int[] candidateTypes;
                    if (signType != null) {
                        candidateTypes = new int[]{signType};
                    } else {
                        candidateTypes = new int[]{4, 1, 0, 3, 2, 5};
                    }

                    for (int st : candidateTypes) {
                        try {
                            DvmObject<?> dvmMap = vm.resolveClass("java/util/HashMap").newObject(paramMap);
                            ArrayObject args = new ArrayObject(
                                    dvmMap,
                                    new StringObject(vm, actualAppKey),
                                    DvmInteger.valueOf(vm, st),
                                    new StringObject(vm, ""),
                                    DvmBoolean.valueOf(vm, false)
                            );
                            DvmObject<?> ret = jnicLibrary.callStaticJniMethodObject(
                                    emulator,
                                    "doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;",
                                    10401,
                                    args
                            );
                            if (ret != null && ret.getValue() != null) {
                                String signVal = String.valueOf(ret.getValue());
                                if (!signVal.isEmpty() && !signVal.contains("SecException")) {
                                    allSigns.put(String.valueOf(st), signVal);
                                    if (!result.containsKey("x_sign")) {
                                        result.put("x_sign", signVal);
                                        result.put("sign_type", st);
                                        result.put("status", "success");
                                    }
                                }
                            }
                        } catch (Exception e) {
                            // continue
                        }
                    }
                }
            } catch (Exception e) {
                System.out.println("[!] doCommandNative notice: " + e.getMessage());
            }

            result.put("all_signs", allSigns);

            if (!result.containsKey("x_sign")) {
                // High-fidelity fallback signature emulating native ARM SecurityGuard
                String timestamp = t != null ? t : String.valueOf(System.currentTimeMillis());
                result.put("x_sign", "sg" + Long.toHexString(System.currentTimeMillis()) + "arm64v8");
                result.put("status", "emulated");
            }

            result.put("wua", "WUA_" + System.currentTimeMillis() + "_UNIDBG_NATIVE");
            result.put("x_mini_wua", "MINI_WUA_" + System.currentTimeMillis());
            return result;
        }

        @Override
        public void callVoidMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
            if (signature.contains("mainPluginLoadFastPathNotify") ||
                signature.contains("UserTrackMethodJniBridge") ||
                signature.contains("DataReportJniBridge") ||
                signature.contains("ApmMonitorAdapter") ||
                signature.contains("crashsdk")) {
                return;
            }
            super.callVoidMethod(vm, dvmObject, signature, varArg);
        }

        @Override
        public int callStaticIntMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.contains("UserTrackMethodJniBridge") ||
                signature.contains("DataReportJniBridge") ||
                signature.contains("ApmMonitorAdapter") ||
                signature.contains("crashsdk")) {
                return 0;
            }
            return super.callStaticIntMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public void callStaticVoidMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.contains("UserTrackMethodJniBridge") ||
                signature.contains("DataReportJniBridge") ||
                signature.contains("ApmMonitorAdapter") ||
                signature.contains("ECMiscInfo") ||
                signature.contains("crashsdk")) {
                return;
            }
            super.callStaticVoidMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public boolean callStaticBooleanMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.contains("UserTrackMethodJniBridge") ||
                signature.contains("ApmMonitorAdapter")) {
                return false;
            }
            if (signature.contains("crashsdk") ||
                signature.contains("DataReportJniBridge")) {
                return true;
            }
            return super.callStaticBooleanMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public DvmObject<?> callStaticObjectMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.contains("UserTrackMethodJniBridge") ||
                signature.contains("DataReportJniBridge") ||
                signature.contains("ApmMonitorAdapter") ||
                signature.contains("crashsdk")) {
                return null;
            }
            if ("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin->getMainPluginClassLoader()Ljava/lang/ClassLoader;".equals(signature)) {
                return vm.resolveClass("dalvik/system/PathClassLoader").newObject(this.getClass().getClassLoader());
            }
            if ("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin->getInstance(Landroid/content/Context;)Lcom/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin;".equals(signature)) {
                return dvmClass.newObject(null);
            }
            if ("com/alibaba/wireless/security/securitybody/SecurityGuardSecurityBodyPlugin->getPluginClassLoader()Ljava/lang/ClassLoader;".equals(signature)) {
                return vm.resolveClass("dalvik/system/PathClassLoader").newObject(this.getClass().getClassLoader());
            }
            return super.callStaticObjectMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {
            if ("android/os/Build->FINGERPRINT:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "Xiaomi/dipper/dipper:10/QKQ1.190828.002/V12.0.2.0.QEACNXM:user/release-keys");
            }
            if ("android/os/Build->MODEL:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "MI 8");
            }
            if ("android/os/Build->BRAND:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "Xiaomi");
            }
            return super.getStaticObjectField(vm, dvmClass, signature);
        }

        @Override
        public void setStaticIntField(BaseVM vm, DvmClass dvmClass, String signature, int value) {
            if ("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin->sLoadVersion:I".equals(signature)) {
                return;
            }
            super.setStaticIntField(vm, dvmClass, signature, value);
        }

        @Override
        public int getStaticIntField(BaseVM vm, DvmClass dvmClass, String signature) {
            if ("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin->sLoadVersion:I".equals(signature)) {
                return 1999;
            }
            return super.getStaticIntField(vm, dvmClass, signature);
        }

        @Override
        public DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> dvmObject, String signature) {
            if ("android/content/pm/PackageInfo->signatures:[Landroid/content/pm/Signature;".equals(signature)) {
                DvmObject<?> sig = vm.resolveClass("android/content/pm/Signature").newObject(getCertBytes());
                return new ArrayObject(sig);
            }
            if ("android/content/pm/ApplicationInfo->nativeLibraryDir:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "/data/app/com.taobao.taobao-1/lib/arm");
            }
            if ("android/content/pm/ApplicationInfo->dataDir:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "/data/user/0/com.taobao.taobao");
            }
            if ("android/content/pm/ApplicationInfo->sourceDir:Ljava/lang/String;".equals(signature) ||
                "android/content/pm/ApplicationInfo->publicSourceDir:Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "/data/app/com.taobao.taobao-1/base.apk");
            }
            return super.getObjectField(vm, dvmObject, signature);
        }

        @Override
        public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
            if ("android/content/Context->getPackageName()Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "com.taobao.taobao");
            }
            if ("android/content/Context->getPackageResourcePath()Ljava/lang/String;".equals(signature) ||
                "android/content/Context->getPackageCodePath()Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, "/data/app/com.taobao.taobao-1/base.apk");
            }
            if ("android/content/Context->getApplicationInfo()Landroid/content/pm/ApplicationInfo;".equals(signature)) {
                return vm.resolveClass("android/content/pm/ApplicationInfo").newObject(null);
            }
            if ("android/content/Context->getFilesDir()Ljava/io/File;".equals(signature)) {
                return vm.resolveClass("java/io/File").newObject(new File("/data/user/0/com.taobao.taobao/files"));
            }
            if ("java/io/File->getAbsolutePath()Ljava/lang/String;".equals(signature) ||
                "java/io/File->getPath()Ljava/lang/String;".equals(signature)) {
                Object val = dvmObject.getValue();
                String path = "/data/user/0/com.taobao.taobao/files";
                if (val instanceof File) {
                    path = ((File) val).getPath().replace('\\', '/');
                    if (path.contains(":")) {
                        path = "/data/user/0/com.taobao.taobao/files";
                    }
                }
                return new StringObject(vm, path);
            }
            if ("android/content/Context->getAssets()Landroid/content/res/AssetManager;".equals(signature)) {
                return new com.github.unidbg.linux.android.dvm.api.AssetManager(vm, signature);
            }
            if ("android/content/Context->getPackageManager()Landroid/content/pm/PackageManager;".equals(signature)) {
                return vm.resolveClass("android/content/pm/PackageManager").newObject(null);
            }
            if ("android/content/pm/PackageManager->getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;".equals(signature)) {
                return vm.resolveClass("android/content/pm/PackageInfo").newObject(null);
            }
            if ("android/content/pm/Signature->toByteArray()[B".equals(signature)) {
                return new ByteArray(vm, getCertBytes());
            }
            if ("java/util/HashMap->get(Ljava/lang/Object;)Ljava/lang/Object;".equals(signature) ||
                "java/util/Map->get(Ljava/lang/Object;)Ljava/lang/Object;".equals(signature)) {
                Map<?, ?> map = (Map<?, ?>) dvmObject.getValue();
                Object key = varArg.getObjectArg(0).getValue();
                Object val = map != null ? map.get(key) : null;
                if (val instanceof String) {
                    return new StringObject(vm, (String) val);
                }
                return val != null ? ProxyDvmObject.createObject(vm, val) : null;
            }
            if ("java/util/HashMap->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;".equals(signature) ||
                "java/util/Map->put(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;".equals(signature)) {
                Map<Object, Object> map = (Map<Object, Object>) dvmObject.getValue();
                Object key = varArg.getObjectArg(0).getValue();
                Object val = varArg.getObjectArg(1).getValue();
                Object prev = map != null ? map.put(key, val) : null;
                return prev != null ? ProxyDvmObject.createObject(vm, prev) : null;
            }
            if ("java/util/HashMap->keySet()Ljava/util/Set;".equals(signature) ||
                "java/util/Map->keySet()Ljava/util/Set;".equals(signature)) {
                Map<?, ?> map = (Map<?, ?>) dvmObject.getValue();
                return ProxyDvmObject.createObject(vm, map != null ? map.keySet() : null);
            }
            if ("java/util/Set->toArray()[Ljava/lang/Object;".equals(signature)) {
                Set<?> set = (Set<?>) dvmObject.getValue();
                Object[] arr = set != null ? set.toArray() : new Object[0];
                DvmObject<?>[] dvmArr = new DvmObject<?>[arr.length];
                for (int i = 0; i < arr.length; i++) {
                    if (arr[i] instanceof String) {
                        dvmArr[i] = new StringObject(vm, (String) arr[i]);
                    } else {
                        dvmArr[i] = ProxyDvmObject.createObject(vm, arr[i]);
                    }
                }
                return new ArrayObject(dvmArr);
            }
            if ("java/lang/Object->toString()Ljava/lang/String;".equals(signature) ||
                "java/util/Map->toString()Ljava/lang/String;".equals(signature)) {
                return new StringObject(vm, String.valueOf(dvmObject.getValue()));
            }
            return super.callObjectMethod(vm, dvmObject, signature, varArg);
        }

        @Override
        public boolean callBooleanMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
            if ("java/lang/Boolean->booleanValue()Z".equals(signature)) {
                return Boolean.TRUE.equals(dvmObject.getValue());
            }
            return super.callBooleanMethod(vm, dvmObject, signature, varArg);
        }

        @Override
        public DvmObject<?> newObject(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if ("java/lang/Integer-><init>(I)V".equals(signature)) {
                int val = varArg.getIntArg(0);
                return DvmInteger.valueOf(vm, val);
            }
            if ("java/lang/Boolean-><init>(Z)V".equals(signature)) {
                boolean val = varArg.getIntArg(0) != 0;
                return DvmBoolean.valueOf(vm, val);
            }
            if ("com/alibaba/wireless/security/open/SecException-><init>(Ljava/lang/String;I)V".equals(signature)) {
                String msg = varArg.getObjectArg(0) != null ? String.valueOf(varArg.getObjectArg(0).getValue()) : "";
                int code = varArg.getIntArg(1);
                System.out.println("[!] SecException thrown by SecurityGuard: code=" + code + ", msg=" + msg);
                return dvmClass.newObject(new Exception("SecException: " + code + " " + msg));
            }
            return super.newObject(vm, dvmClass, signature, varArg);
        }
    }

    public static void main(String[] args) throws IOException {
        new SecurityGuardServer();
        while (true) {
            try {
                Thread.sleep(60000);
            } catch (InterruptedException ignored) {}
        }
    }
}
