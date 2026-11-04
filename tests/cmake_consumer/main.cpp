// 只验证「能 include、能链接」，不断言消息表内容——消息表由算法组与电控组共同
// 确定，会随时间变化，不应让消费方冒烟跟着红。
#include "lower_link.hpp"

int main() {
    const auto size = foray::lower_link::expected_payload_size(foray::lower_link::MsgId{0});
    (void)size;
    return 0;
}
