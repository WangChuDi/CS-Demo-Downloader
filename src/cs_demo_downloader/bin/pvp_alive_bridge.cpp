// 32-bit Windows bridge for PvpAlive.dll swapData.
//
// Usage:
//   pvp_alive_bridge.exe <PvpAlive.dll> <inner_json>
//
// The bridge prints the swapData output to stdout and diagnostics to stderr.
// It must be compiled as a 32-bit Windows executable because PvpAlive.dll is
// a 32-bit DLL.

#ifdef _WIN32
#include <windows.h>
#endif

#include <cstdio>
#include <cstring>
#include <string>

namespace {

using SwapDataFn = int(__cdecl *)(const char*, unsigned, char*, unsigned*);

std::string last_error_message() {
#ifdef _WIN32
    DWORD error = GetLastError();
    if (error == 0) {
        return "unknown error";
    }

    char* message_buffer = nullptr;
    DWORD size = FormatMessageA(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr,
        error,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<char*>(&message_buffer),
        0,
        nullptr
    );
    std::string message = size && message_buffer ? message_buffer : "unknown error";
    if (message_buffer) {
        LocalFree(message_buffer);
    }
    while (!message.empty() && (message.back() == '\r' || message.back() == '\n')) {
        message.pop_back();
    }
    return message;
#else
    return "not a Windows build";
#endif
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: pvp_alive_bridge.exe <PvpAlive.dll> <inner_json>\n");
        return 2;
    }
    if (argc < 3) {
        std::fprintf(stderr, "missing inner_json argument\n");
        return 2;
    }

#ifndef _WIN32
    std::fprintf(stderr, "pvp_alive_bridge requires Windows and a 32-bit build.\n");
    return 2;
#else
    const char* dll_path = argv[1];
    const char* inner_json = argv[2];
    const std::string dll_path_string(dll_path);
    const std::string::size_type slash = dll_path_string.find_last_of("\\/");
    const std::string dll_dir = slash == std::string::npos ? std::string(".") : dll_path_string.substr(0, slash);

    SetDllDirectoryA(dll_dir.c_str());
    HMODULE dll = LoadLibraryA(dll_path);
    if (dll == nullptr) {
        std::fprintf(stderr, "failed to load DLL: %s: %s\n", dll_path, last_error_message().c_str());
        return 1;
    }

    FARPROC proc = GetProcAddress(dll, "swapData");
    if (proc == nullptr) {
        std::fprintf(stderr, "failed to find swapData export: %s\n", last_error_message().c_str());
        FreeLibrary(dll);
        return 1;
    }

    auto swap_data = reinterpret_cast<SwapDataFn>(proc);
    char output[512] = {0};
    unsigned output_len = static_cast<unsigned>(sizeof(output));
    const unsigned input_len = static_cast<unsigned>(std::strlen(inner_json));
    const int result = swap_data(inner_json, input_len, output, &output_len);
    if (result == 0) {
        std::fprintf(stderr, "swapData failed\n");
        FreeLibrary(dll);
        return 1;
    }
    if (output_len > sizeof(output)) {
        std::fprintf(stderr, "swapData output length exceeds bridge buffer\n");
        FreeLibrary(dll);
        return 1;
    }

    std::fwrite(output, 1, output_len, stdout);
    std::fputc('\n', stdout);
    FreeLibrary(dll);
    return 0;
#endif
}
