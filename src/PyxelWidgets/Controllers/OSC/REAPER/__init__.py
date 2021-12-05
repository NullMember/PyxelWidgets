import PyxelWidgets.Controllers.OSC

class REAPER(PyxelWidgets.Controllers.OSC.OSC):
    def __init__(self, ip, in_port=8000, out_port=9000, **kwargs):
        super().__init__(ip, in_port=in_port, out_port=out_port, **kwargs)
        self.messages = {
            "Update" : "/update",
            "Crossfade" : "/crossfade",
            "ProjectName" : "/project/name",
            "ProjectEngine" : "/project/engine",
            "Play" : "/play",
            "Record" : "/record",
            "Repeat" : "/repeat",
            "Click" : "/click",
            "ClickVolume" : "/click/volume"
        }