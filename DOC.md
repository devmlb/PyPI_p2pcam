# Reverse-Engineered Protocol Notes

This document explains the technical details of the protocol used by the cameras, as discovered through the decompilation of SDKs found on the internet ([here](https://github.com/jameshilliard/android-p2p-sdk3.0) and [here](https://github.com/jameshilliard/HKiPhoneSDKDemo20160621)) and the analysis of network packets using Wireshark. It may therefore contain approximations resulting from reverse engineering, whilst the manufacturer has undoubtedly defined its protocol more precisely.  
All the data presented here is implemented in the files `p2pcam/lan_scanner.py` and `p2pcam/lan_video.py`.

## Discovery Process

Camera discovery uses a UDP broadcast exchange on port `2627`.

The scanner emits a discovery packet with this exact layout:

```text
[0-1]   00 00
[2-3]   struct.pack("<H", (len(inner) + 4) << 4)
[4-12]  inner packet header
[13+]   ASCII dictionary body
```

The refresh body is built by `_encode_old_dict()` from these fields:

```text
TIME=3600;
endTime=<unix_time_plus_3600>;
MainCmd=LocalData;
userType=hkclient;
status=1;
Prot=<listen_port>;
MacIP=<random_marker>;
```

The code sends that packet to `255.255.255.255` and to each interface broadcast address derived from the host IPv4 interfaces. The exact packet template is:

```text
00 00 <len_lo> <len_hi>
<command<<4 | 0x02> 0C 1D <inner_len_lo> <inner_len_hi> 00 00 00 00>
TIME=3600;endTime=...;MainCmd=LocalData;userType=hkclient;status=1;Prot=<listen_port>;MacIP=<random_marker>;
```

Responses are collected on the source port and, optionally, a separate listen port. The decoder accepts two packet families:

1. framed replies that start with `00 00` and store the packet length in the shifted outer-length field
2. inner discovery packets where `data[0] >> 4 == COMMAND_LAN_REFRESH` and the dictionary body begins at byte 9

Parsed fields are normalized into `LanDevice` objects by reading aliases for the same concept. For example, `HKID`, `hkid`, `DevID`, and `DSTHKID` are treated as the device identifier family, while `Prot`, `UDPPort`, `Port`, and `port` are treated as the network port family.

The scanner ignores its own discovery echo by checking the `MacIP` field against the locally generated marker. It also recognizes 13-byte ACK packets using `_decode_ack()` and turns them into a simple online/status marker:

```text
00 00 d0 00 <cmd_lo> <flag> 20 09 00 <pipe_lo> <pipe_hi> 00 00
```

The result of discovery is a list of devices sorted by device ID and HKID.

## Streaming

Video streaming uses UDP port `5000` and follows a strict handshake/state machine before MJPEG data starts flowing.

Every framed packet in this phase uses `_build_packet()`:

```text
[0-1]   packet counter (uint16 LE)
[2-3]   outer length = total_packet_len << 4
[4]     inner_cmd
[5]     inner_flag1
[6]     inner_flag2
[7-8]   inner payload length
[9-12]  inner_extra (4 bytes)
[13+]   payload body
```

The streaming sequence is exactly:

1. send the connection ping packets several times until the camera acknowledges
2. send `HK_RES_REQ` to request the video session
3. poll with `ICMD2` until the camera answers with `SessionCreate`
4. send `SessionStart`
5. receive MJPEG chunks, ACK camera `ICMD1` polls, and periodically send continue packets
6. stop cleanly with `SessionDelete`

The exact packet builders are:

```text
Ping 1:
00 00 d0 00 82 0c 00 09 00 d1 07 00 00

Ping 2:
00 00 d0 00 a2 0c 40 09 00 d1 07 00 00

HK_RES_REQ body:
id=<hkid>;ftN0=video.vbVideo.MPEG4;ftN1=net.0;ftN2=HKPCPresent.HKPCPresent;opN2=<sid>;Callid=<callid>;sidN=<sid>;AsCode=337;MainCmd=HK_RES_REQ;user=Lan user;

ICMD2 poll body:
d4:ICMD2:293:SEQ1:<hkid>:GUARDSEQ1:<seq>

SessionStart body:
MainCmd=SessionStart;sidN=<sid>;ftN0=HKPCPresent.HKPCPresent;FD0=4;ftN1=net.1024;FD1=1024;

ICMD1 ACK body:
d4:ICMD1:293:lastreq1:<hkid>:SEQ3:<seq>e

SessionDelete body:
sidN=<sid>;MainCmd=SessionDelete;coz=;
```

Those bodies are encoded exactly as follows:

- dictionary-style packets keep the first 2 bytes in plain ASCII and XOR the remaining bytes with `0xE9`
- `ICMD`-style packets XOR every byte with `0xE9`

The `HK_RES_REQ`, `SessionStart`, `ICMD1` ACK, `ICMD2` poll, and `SessionDelete` builders all follow those rules. The code uses a fixed session identifier and call identifier because those values are hard-coded defaults in the implementation.

After `SessionCreate`, the camera begins sending MJPEG fragments. The assembler takes `data[4:]` as the payload, looks for `FF D8` to start a frame, and looks for `FF D9` to close it. If `_in_frame` is already true, the payload is appended before searching for EOI.

Two additional keepalive mechanisms are required while streaming:

- the client replies to camera `ICMD1` polls with `_build_icmd1_ack(hkid, seq, session_id)`
- the client sends `cont_state.next_packet()` every 5 received fragments

The continue packet builder is intentionally stateful because the camera expects the exact `_ContinueState` sequence: `nb_digits`, `idx`, `base_index`, and `_fragment_index` are mutated across calls, bytes `[2]` and `[7]` are rewritten for the current digit width, and the packet ends with `_CONT_END`.

When the stream ends, the client sends `SessionDelete` so the camera releases the session and the next connection attempt starts from a clean state.