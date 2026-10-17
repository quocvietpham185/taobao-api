import frida
import time
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("rpc_signer")

FRIDA_RPC_SCRIPT = r"""
var mtopInst = null;
var mtopConfig = null;
var ttid = null;
var appKey = null;

Java.perform(function() {
    try {
        var Mtop = Java.use("mtopsdk.mtop.intf.Mtop");
        var currentApp = Java.use("android.app.ActivityThread").currentApplication();
        var ctx = currentApp.getApplicationContext();
        mtopInst = Mtop.instance("INNER", ctx);
        mtopConfig = mtopInst.getMtopConfig();
        ttid = "" + mtopConfig.ttid.value;
        appKey = "" + mtopConfig.appKey.value;
    } catch(e) {}
});

rpc.exports = {
    executeapi: function(api, v, dataJsonStr) {
        return new Promise(function(resolve, reject) {
            Java.perform(function() {
                try {
                    var MtopRequest = Java.use("mtopsdk.mtop.domain.MtopRequest");
                    var req = MtopRequest.$new();
                    req.setApiName(String(api));
                    req.setVersion(String(v));
                    req.setData(String(dataJsonStr));
                    req.setNeedEcode(false);
                    req.setNeedSession(false);

                    var buildMethod = mtopInst.build.overload('mtopsdk.mtop.domain.MtopRequest', 'java.lang.String');
                    var builder = buildMethod.call(mtopInst, req, ttid);
                    builder.useWua();

                    var resp = builder.syncRequest();
                    var retCode = resp.getRetCode() ? ("" + resp.getRetCode()) : "";
                    var retMsg = resp.getRetMsg() ? ("" + resp.getRetMsg()) : "";
                    var respCode = resp.getResponseCode();

                    var byteData = resp.getBytedata();
                    var bodyStr = "";
                    if (byteData != null) {
                        var StringCls = Java.use("java.lang.String");
                        bodyStr = "" + StringCls.$new(byteData, "UTF-8");
                    }

                    resolve({
                        status_code: respCode,
                        ret_code: retCode,
                        ret_msg: retMsg,
                        body: bodyStr
                    });
                } catch(err) {
                    reject("" + err.stack);
                }
            });
        });
    },

    signpayload: function(api, v, data, t) {
        return new Promise(function(resolve, reject) {
            Java.perform(function() {
                try {
                    var rawSignObj = mtopConfig.sign.value;
                    var signObj = Java.cast(rawSignObj, Java.use("tb.n9f"));
                    var HashMap = Java.use("java.util.HashMap");

                    var map = HashMap.$new();
                    map.put("api", String(api));
                    map.put("v", String(v));
                    map.put("data", String(data));
                    map.put("t", String(t));
                    map.put("appKey", mtopConfig.appKey.value);

                    var resMap = signObj.r(map, null, mtopConfig.appKey.value, null, false, null);
                    var out = {
                        appKey: "" + mtopConfig.appKey.value,
                        utdid: "" + mtopConfig.utdid.value,
                        ttid: "" + mtopConfig.ttid.value,
                        deviceId: "" + mtopConfig.deviceId.value,
                        signs: {}
                    };

                    if (resMap != null) {
                        var iter = resMap.keySet().iterator();
                        while (iter.hasNext()) {
                            var k = iter.next();
                            var val = resMap.get(k);
                            out.signs["" + k] = val ? ("" + val) : "";
                        }
                    }
                    resolve(out);
                } catch(err) {
                    reject("" + err);
                }
            });
        });
    }
};
"""

class RpcSigner:
    _instance: Optional['RpcSigner'] = None

    def __init__(self):
        self.device = None
        self.session = None
        self.script = None
        self.rpc = None
        self._connected = False

    @classmethod
    def get_instance(cls) -> 'RpcSigner':
        if cls._instance is None:
            cls._instance = RpcSigner()
        return cls._instance

    def connect(self) -> bool:
        try:
            self.device = frida.get_usb_device()
            procs = [p for p in self.device.enumerate_processes() if "淘" in p.name or "taobao" in p.name.lower()]
            if not procs:
                logger.error("Taobao process not found on device!")
                return False
            
            target_pid = procs[0].pid
            logger.info(f"Attaching to Taobao PID {target_pid}...")
            self.session = self.device.attach(target_pid)
            self.script = self.session.create_script(FRIDA_RPC_SCRIPT)
            self.script.load()
            self.rpc = self.script.exports_sync
            self._connected = True
            logger.info("Frida RPC Signer attached and initialized successfully!")
            return True
        except Exception as e:
            logger.error(f"Failed to connect Frida RPC Signer: {e}")
            self._connected = False
            return False

    def is_connected(self) -> bool:
        return self._connected

    def execute_api(self, api: str, v: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self._connected:
            if not self.connect():
                raise RuntimeError("Cannot connect to Taobao RPC node")

        data_str = json.dumps(data, separators=(',', ':'))
        try:
            result = self.rpc.executeapi(api, v, data_str)
            return result
        except Exception as e:
            logger.warning(f"RPC execute error ({e}), attempting reconnect...")
            self.connect()
            return self.rpc.executeapi(api, v, data_str)

    def sign_payload(self, api: str, v: str, data_str: str, t: str) -> Dict[str, Any]:
        if not self._connected:
            if not self.connect():
                raise RuntimeError("Cannot connect to Taobao RPC node")

        try:
            return self.rpc.signpayload(api, v, data_str, t)
        except Exception as e:
            logger.warning(f"RPC sign error ({e}), attempting reconnect...")
            self.connect()
            return self.rpc.signpayload(api, v, data_str, t)
