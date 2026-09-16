// Cpp_Hub 可运行入口（占位）
// 中文命名文件：O-06 中文路径/文件名验证样本
#include <iostream>
#include <vector>
#include <string>
#include "因子计算_核心.cpp"

int main(int argc, char** argv) {
  // Mean mode: single argument "--mean"
  if (argc == 2 && std::string(argv[1]) == "--mean") {
    std::vector<double> values;
    double x;
    while (std::cin >> x) {
      values.push_back(x);
    }
    double mean = cpphub::向量均值(values);
    std::cout << "均值=" << mean << std::endl;
    return 0;
  }

  const int a = (argc > 1) ? std::stoi(argv[1]) : 3;
  const int b = (argc > 2) ? std::stoi(argv[2]) : 4;
  std::cout << "因子求和(" << a << "," << b << ") = "
            << cpphub::因子求和(a, b) << std::endl;
  return 0;
}