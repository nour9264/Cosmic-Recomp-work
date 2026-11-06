// Synthetic collector checks only. Does not start a game or GPU.
#include "../native-rex/src/shared_memory_audit.h"
#include <cassert>
#include <cmath>
#include <iostream>

int main(int argc,char** argv) {
  using namespace ben10_shared_audit;
  if(argc!=2)return 2;
  if(std::string(argv[1])=="disabled") {
    if(totals.enabled())return 3;
    {Request request(1);request.Mark(LockWait);request.succeeded=true;}
    if(totals.requests || totals.request_ms!=0)return 4;
    std::cout<<"Disabled collector remained inactive.\n";return 0;
  }
  if(!totals.enabled())return 5;
  {
    Request request(1);request.Mark(Allocation);totals.requested_bytes+=4096;
    request.Mark(LockWait);request.Mark(PageScan);++totals.scanned_blocks;
    request.Mark(Finish);++totals.valid_without_upload;request.succeeded=true;
  }
  {Request request(1);}
  {
    Request request(2);request.Mark(UploadInclusive);
    {UploadSpan span(Memcpy);totals.uploaded_bytes+=8192;}
    ++totals.upload_ranges;request.succeeded=true;
  }
  if(totals.requests!=3 || totals.ranges!=4 || totals.failed!=1)return 6;
  double sum=0;for(double value:totals.phase_ms)sum+=value;
  if(std::abs(sum-totals.request_ms)>0.000001)return 7;
  totals.start-=std::chrono::seconds(6);totals.Flush(Clock::now());
  if(totals.requests || totals.failed || totals.request_ms!=0)return 8;
  if(!std::filesystem::exists(totals.output))return 9;
  std::cout<<"Collector counts, phase partition, flush and reset passed.\n";
}
