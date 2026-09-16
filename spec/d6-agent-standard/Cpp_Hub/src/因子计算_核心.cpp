// 因子计算核心模块（Cpp_Hub 试点占位实现）
// 用途：O-06 中文文件/路径名跨站传输验证样本 + Cpp_Hub 骨架
#pragma once
#include <vector>

namespace cpphub {

// 占位求和：验证编译链（cmake/g++/libstdc++）就绪的最小可执行逻辑
inline int 因子求和(const int a, const int b) { return a + b; }

inline double 向量均值(const std::vector<double>& v) {
  if (v.empty()) return 0.0;
  double sum = 0.0;
  for (double d : v) sum += d;
  return sum / v.size();
}
 }  // namespace cpphub